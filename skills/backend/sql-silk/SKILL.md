---
name: sql-silk
description: SQL database standards for Python backends using PostgreSQL, MySQL or SQLite with SQLAlchemy 2.0 (Flask, FastAPI) or the Django ORM. Covers the generic DBService with short sessions (create, read, update, delete with commit and rollback), engine and connection-pool setup, models with audit fields and named constraints, Alembic, Flask-Migrate and Django migrations, filtering, search and pagination queries, avoiding N+1 queries, and mapping IntegrityError and OperationalError to 409 and 424. Use this whenever a project touches a relational database, defines or changes models, writes queries, adds a migration, or hits errors like "column does not exist", "QueuePool limit reached", AmbiguousForeignKeysError or DetachedInstanceError, even if the user doesn't say SQL. Apply together with backend-silk and the framework spider.
---

# SQL Silk: relational database standards

Shared SQL rules for every framework spider. `backend-silk` decides the layers; this skill decides how the database layer works. Django projects use the ORM directly (see `references/django-orm.md`); everything else here is SQLAlchemy 2.0.

## The core idea

**Each database operation runs in its own short session that always ends.** A SQLAlchemy session holds a pooled connection from its first query until `commit()`, `rollback()` or `close()`. If a session stays open while the request waits on an LLM, another API or file processing, that connection does nothing for seconds, and when the pool is exhausted the next request fails with `QueuePool limit ... reached`. So:

- The engine (connection pool) is created **once** at startup and disposed at shutdown.
- A generic `DBService` owns all sessions. Each of its methods opens a session, does one unit of work, commits or rolls back, and closes. Routes and helpers never see a session.
- No `Depends(get_db)` session that lives for the whole request.

## Layers

| Who | Does |
|---|---|
| Helper | Builds the feature query: `select(Expense).where(Expense.user_id == user_id, ...)`, filters, search, sort, pagination; checks ownership; maps `IntegrityError` to 409 |
| `DBService` (`app/services/db_service.py`) | Engine and pool lifecycle; `create`, `read`, `update`, `delete`; commit and rollback |
| `ErrorHandlers` | `OperationalError` (database unreachable) and "database not configured" → 424 |

DBService stays generic. A method that only one feature uses (`get_filtered_expenses`) belongs in that feature's helper, not in DBService.

## DBService: four methods

Templates: `assets/db_service_async.py` (FastAPI) and `assets/db_service_sync.py` (Flask, or sync FastAPI with `def` routes).

| Method | Does |
|---|---|
| `create(record_or_list)` | Inserts one record, or a list in **one** transaction; refreshes and returns them |
| `read(statement, one=False)` | Runs a `select`; `one=True` returns a single object, a scalar (counts) or `None` |
| `update(record, changes=None)` | Merges a record loaded earlier, applies `changes`, commits, returns the fresh record |
| `delete(record)` | Merges and deletes a record, commits |

Usage from a helper:

```python
statement = select(Expense).where(Expense.user_id == user_id)
statement = cls.apply_expense_filters(statement, filters)
total = await DBService.read(select(func.count()).select_from(statement.order_by(None).subquery()), one=True)
expenses = await DBService.read(statement.order_by(Expense.created_at.desc(), Expense.id.desc()).offset((page - 1) * page_size).limit(page_size))
```

Rules that keep short sessions safe:

1. **Writes that must succeed together** (two new rows) go in one `create([...])` call. If a feature truly needs different operations in one transaction (update one row and insert another), add a single `transaction` method to DBService at that point, not before.
2. **Detached objects.** The session factory uses `expire_on_commit=False`, so loaded columns stay readable after the session closes. Relationships are not: load the ones a response needs inside the query (`selectinload(Ticket.comments)`). Touching an unloaded relationship later raises `DetachedInstanceError`.
3. **Updates and deletes use `merge`**, because the record was loaded in an earlier session. It costs one primary-key lookup.
4. **Async apps use the async engine.** Never call the sync DBService from an `async def` route; it blocks every other request.
5. **flush vs commit**: `commit()` flushes automatically, so DBService only commits. `flush()` sends SQL inside the open transaction without finishing it; use it only when you need a generated id inside a bigger transaction.

## Engine and pool

- Driver URLs: PostgreSQL async (FastAPI) `postgresql+asyncpg://`, sync (Flask) `postgresql+psycopg://`; MySQL `mysql+asyncmy://` / `mysql+pymysql://`; SQLite `sqlite+aiosqlite:///` / `sqlite:///`.
- **Not async psycopg on Windows**: uvicorn runs on `ProactorEventLoop` there, and psycopg's async mode refuses it (`InterfaceError: Psycopg cannot use the 'ProactorEventLoop'`), so every query fails. `asyncpg` works on every platform (tested).
- Pool settings from `.env` through `config.py`: `DB_POOL_SIZE` (5), `DB_MAX_OVERFLOW` (10), `DB_POOL_TIMEOUT` (30), plus `pool_pre_ping=True` and `pool_recycle=1800`. Add these fields to the project's `AppConfig` and `.env.example` together with `DATABASE_URL`. SQLite URLs get no pool options.
- Keep `workers × (pool_size + max_overflow)` below the server's `max_connections` (PostgreSQL default 100).
- No ping on every request; `/health` runs `SELECT 1` through DBService.
- A missing `DATABASE_URL` or unreachable server does not stop a FastAPI app from starting; DB endpoints return 424. (Flask-SQLAlchemy requires the URL at startup; that is the one exception.)

Details and the library comparison: `references/connection-pooling.md`.

## Models

- SQLAlchemy 2.0 typed style: `Mapped[...]` and `mapped_column(...)`, `DeclarativeBase` with a **naming convention** so every constraint has a name (unnamed constraints break `downgrade`). Template: `assets/base.py`.
- Explicit `__tablename__`, plural snake_case (`users`, `expenses`); foreign keys point at it (`ForeignKey("users.id")`, not `"user.id"`).
- Timestamps timezone-aware UTC: `created_at`, `updated_at` (with `onupdate`). Audit `created_by` / `updated_by` as nullable FKs with `ondelete="SET NULL"`, set from the token. Use the mixins in `assets/base.py` instead of repeating the columns.
- Money `Numeric(12, 2)`, never float. `CheckConstraint` for invariants (`amount > 0`). `unique=True` and indexes on columns used in filters, lookups and ownership checks.
- Several FKs to the same table (owner, created_by, updated_by): set `foreign_keys=[...]` on every relationship or SQLAlchemy raises `AmbiguousForeignKeysError`.
- Owner FK `ondelete="CASCADE"` only when child rows really belong to the parent; otherwise `RESTRICT`.

## Migrations

- Every schema change goes through migrations (Alembic, Flask-Migrate or Django), committed together with the model change. Never use `create_all()` instead.
- Always read the autogenerated script before applying it.
- Never edit a migration that is already applied anywhere; write a new one.
- Adding a NOT NULL column to a table that has rows: add it nullable (or with a `server_default`), backfill with `UPDATE`, then make it NOT NULL.
- "column does not exist" or similar drift: check `alembic current` / `flask db current` / `showmigrations` and the real table before touching code.
- Resetting the database is only for a disposable local database, and only with the user's go-ahead.

Commands and the safe patterns: `references/migrations.md`.

## Queries

- SQLAlchemy 2.0 style only: `select()`, `where()`, `func`. No legacy `Model.query`, no string-built SQL.
- Filter, search, count and paginate in the database, never in Python.
- Search with `ilike` (PostgreSQL) on indexed text columns; order deterministically with a unique tiebreaker.
- Avoid N+1: eager-load relationships the response uses (`selectinload` for collections, `joinedload` for single parents).
- Check existence with `select(exists().where(...))` or a `limit(1)` query, not by loading lists.

Patterns and the full list-endpoint example: `references/querying.md`.

## Errors

| Exception | Where handled | Response |
|---|---|---|
| `IntegrityError` on a unique constraint | Helper, around `create`/`update`; check the constraint name (`exc.orig.diag.constraint_name` with psycopg) | 409 "Email is already registered." |
| `IntegrityError` other (FK, check) | Helper if expected, otherwise global handler | 400 or 500 |
| `OperationalError`, `ConnectionError` (asyncpg raises the built-in `ConnectionRefusedError` when the server is down; DBService raises `ConnectionError("Database is not configured.")`) | `ErrorHandlers.handle_database_exception` | 424 "Database dependency is unavailable." |
| Pool timeout (`sqlalchemy.exc.TimeoutError`) | `ErrorHandlers` | 503, and investigate long-held sessions |

DBService rolls back and re-raises; it never swallows or translates errors. Log the error type, never the connection string.

## Reference files

| File | Read when |
|---|---|
| `references/connection-pooling.md` | Setting up the engine, pool errors, sync vs async, comparing DB libraries |
| `references/migrations.md` | Creating or fixing migrations, schema drift |
| `references/querying.md` | List endpoints, filters, search, pagination, joins, aggregates |
| `references/django-orm.md` | Any Django project |

## Assets

| File | Becomes |
|---|---|
| `assets/db_service_async.py` | `app/services/db_service.py` (FastAPI) |
| `assets/db_service_sync.py` | `app/services/db_service.py` (Flask / sync) |
| `assets/base.py` | `app/models/base.py` |
