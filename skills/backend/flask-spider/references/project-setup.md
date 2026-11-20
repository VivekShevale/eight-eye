# Project Setup

## Contents
1. Copy map
2. Build order
3. Commands (Windows)
4. Flask-Migrate
5. .env.example additions

## 1. Copy map

| Project file | Source |
|---|---|
| `run.py`, `requirements.txt` | `flask-spider/assets/project/` |
| `app/__init__.py`, `app/config.py`, `app/extensions.py` | `flask-spider/assets/project/app/` |
| `app/services/db_service.py` | `flask-spider/assets/project/app/services/` (Flask variant of the sql-silk DBService) |
| `app/utils/error_handlers.py`, `auth_utils.py`, `request_utils.py` | `flask-spider/assets/project/app/utils/` |
| `app/utils/log_utils.py` | `backend-silk/assets/log_utils.py` with `SERVER_LOGGERS = ("werkzeug",)` |
| `app/schemas/common_schema.py` | `backend-silk/assets/common_schema.py` |
| `app/models/base.py` | `sql-silk/assets/base.py` |
| Health: `health_routes.py`, `health_helper.py`, `health_schema.py` | `flask-spider/assets/project/app/...` |
| Auth: `auth_routes.py`, `auth_helper.py`, `auth_schema.py`, `models/user.py` | `flask-spider/assets/project/app/...` |
| Example feature: `expense_*` files, `models/expense.py` | `flask-spider/assets/project/app/...` |
| `.env.example`, `.gitignore` | `backend-silk/assets/env.example`, `backend-silk/assets/gitignore` (only the keys and sections this project uses) |
| `app/models/__init__.py` | Starter version (empty with a comment); all other `__init__.py` empty |

`app/__init__.py` imports only the blueprints and models that exist.

## 2. Build order (what depends on what)

1. **Skeleton**: requirements, config, log utils, common schema, error handlers, request utils, extensions, DBService, health blueprint, `create_app`, `run.py`. Expected: `/health` 200 with the DB running, 424 with it stopped.
2. **Database**: `models/base.py`, `models/user.py`, `flask db init`, first migration.
3. **Auth**: auth schema, utils, helper, blueprint. Expected: register 201, duplicate 409, login, wrong password 401, `/me` 401 without a token.
4. **Each feature**: routes decided first, then model + migration, schemas, helper, blueprint.
5. README with setup and run steps.

## 3. Commands (Windows)

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
flask --app run.py db upgrade
flask --app run.py run --debug
```

## 4. Flask-Migrate

```bat
flask --app run.py db init
flask --app run.py db migrate -m "create users table"
flask --app run.py db upgrade
flask --app run.py db current
```

- `migrate.init_app(app, db, render_as_batch=...)` in the starter turns on batch mode for SQLite, which can't alter tables in place.
- The naming convention on `Base` names every constraint (`uq_users_email`, `fk_expenses_user_id_users`), so `downgrade()` works and `IntegrityError` handlers can check names.
- A model that no blueprint imports must still be imported in `app/__init__.py`, or autogenerate won't see it.
- Read every generated script before `upgrade`; the safe patterns for NOT NULL columns, renames and drift are in `sql-silk/references/migrations.md`.

## 5. .env.example additions

On top of `backend-silk/assets/env.example`:

```env
# Flask-SQLAlchemy needs this at startup
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/DB_NAME

# SQL connection pool (per worker process)
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
```

`JWT_ALGORITHM` from the shared example isn't used by Flask-JWT-Extended's defaults (HS256); drop it from a Flask project's `.env.example`.
