# Connection Pooling

## Contents
1. Engine, pool and session
2. When a connection is held
3. Why not `Depends(get_db)` for the whole request
4. Pool sizing
5. Sync vs async
6. How other database libraries behave
7. SQLite notes

## 1. Engine, pool and session

| Object | Created | Lives |
|---|---|---|
| Engine (owns the pool) | Once, at startup (`DBService.connect()` in lifespan / app factory) | Until shutdown (`dispose()`) |
| Pooled connection | Lazily, when a session first needs one, up to `pool_size + max_overflow` | Reused; returned to the pool after each transaction |
| Session | Per DBService call | Milliseconds: open → query/commit → close |

Opening a new engine or connection per query or per request is never done in production: every call pays TCP, auth and TLS setup (10–200 ms instead of ~1 ms) and bursts of traffic exhaust the server's connection limit.

## 2. When a connection is held

A SQLAlchemy session borrows a connection at its **first query** (reads too, because a transaction starts automatically) and keeps it until `commit()`, `rollback()` or `close()`.

```text
session opened        -> no connection yet
first query           -> connection borrowed, transaction open
... slow LLM call ... -> connection still held, doing nothing
commit / close        -> connection returned
```

DBService closes the session at the end of every method, so a connection is held only for the few milliseconds of that operation.

## 3. Why not `Depends(get_db)` for the whole request

```python
async def get_db():
    async with SessionLocal() as session:
        yield session   # held until the response is sent
```

With this dependency, a route that reads, then calls an LLM for 5 seconds, then writes, keeps one connection the whole 5 seconds. With a pool of 15, the 16th concurrent request waits `pool_timeout` seconds and fails. Use DBService with its own short sessions instead of a request-scoped session. Auth dependencies follow the same rule: they read the user through DBService and return a plain value.

## 4. Pool sizing

| Setting | Default here | Meaning |
|---|---|---|
| `pool_size` | 5 | Connections kept open |
| `max_overflow` | 10 | Extra connections allowed under load |
| `pool_timeout` | 30 | Seconds to wait for a free connection before `TimeoutError` |
| `pool_pre_ping` | True | Checks a connection is alive before using it (survives DB restarts) |
| `pool_recycle` | 1800 | Replaces connections older than 30 min (avoids server-side idle disconnects) |

- The limit counts queries running at the same instant, not logged-in users. Hundreds of users fit in a pool of 15 because each holds a connection for milliseconds.
- Each worker process has its own pool: `workers × (pool_size + max_overflow)` must stay below the database's `max_connections` (PostgreSQL default 100; managed tiers have their own caps).
- Many workers or many app instances: put PgBouncer in front of PostgreSQL.
- Values come from `.env` (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`) via `config.py`:

```python
db_pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
db_max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
db_pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
```

## 5. Sync vs async

| App | Engine | DBService | Routes |
|---|---|---|---|
| FastAPI (default) | `create_async_engine("postgresql+asyncpg://...")` (not async psycopg: it fails on Windows' ProactorEventLoop) | `assets/db_service_async.py`, `await DBService.read(...)` | `async def` |
| FastAPI, sync code base | `create_engine(...)` | `assets/db_service_sync.py` | plain `def` (FastAPI runs them in a thread pool) |
| Flask | Flask-SQLAlchemy engine (`db.engine`) | sync, sessions on `db.engine` | plain functions |
| Django | Django-managed | none | views |

Never call a sync database function inside `async def`: it blocks the event loop and every other request waits.

## 6. How other database libraries behave

| Library | Connection is held |
|---|---|
| SQLAlchemy ORM `Session`, SQLModel | From first query until commit/rollback/close |
| SQLAlchemy Core `engine.connect()` | Until the block ends |
| asyncpg `pool.fetch()` | Per query |
| asyncpg / aiomysql `pool.acquire()`, psycopg `pool.connection()` | Until the block ends |
| Django ORM | Per request/thread, reused with `CONN_MAX_AGE` |
| PyMongo `MongoClient` / `AsyncMongoClient` | Per operation (see `mongodb-silk`) |
| redis-py | Per command (pipelines and pub/sub hold one) |

The general rule for any database: an open transaction keeps a connection busy, so never keep one open across slow work.

## 7. SQLite notes

- A file, not a server: no network pool, one writer at a time.
- Fine for local development and small Django projects; use PostgreSQL for anything multi-user.
- Never commit `db.sqlite3`.
- Async: `sqlite+aiosqlite:///./app.db`.
- DBService passes no pool options for SQLite URLs (the async driver uses `NullPool` and rejects `pool_size`).
- SQLite stores datetimes without a time zone; values read back are naive even with `DateTime(timezone=True)`. PostgreSQL keeps the zone.
