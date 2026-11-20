# Project Setup

## Contents
1. Copy map
2. Build order
3. Commands (Windows)
4. Alembic with the async engine
5. MongoDB instead of SQL
6. .env.example additions

## 1. Copy map

| Project file | Source |
|---|---|
| `app/main.py`, `app/config.py` | `fastapi-spider/assets/project/app/` |
| `app/utils/error_handlers.py`, `app/utils/auth_utils.py` | `fastapi-spider/assets/project/app/utils/` |
| `app/utils/log_utils.py` | `backend-silk/assets/log_utils.py` |
| `app/schemas/common_schema.py` | `backend-silk/assets/common_schema.py` |
| `app/models/base.py` | `sql-silk/assets/base.py` |
| `app/services/db_service.py` | `sql-silk/assets/db_service_async.py` |
| `app/services/mongodb_service.py` (MongoDB projects) | `mongodb-silk/assets/mongodb_service.py` |
| `app/routes/health_routes.py`, `app/helpers/health_helper.py`, `app/schemas/health_schema.py` | `fastapi-spider/assets/project/app/...` |
| Auth: `auth_routes.py`, `auth_helper.py`, `auth_schema.py`, `models/user.py` | `fastapi-spider/assets/project/app/...` |
| Example feature: `expense_*` files, `models/expense.py` | `fastapi-spider/assets/project/app/...` (pattern to copy for real features) |
| `requirements.txt` | `fastapi-spider/assets/project/requirements.txt` |
| `.env.example`, `.gitignore` | `backend-silk/assets/env.example`, `backend-silk/assets/gitignore` (only the keys and sections this project uses) |
| every `app/**/__init__.py` | empty, except `app/models/__init__.py` which imports all models |

Copy only the files the project needs; `main.py` includes only the routers that exist.

## 2. Build order (what depends on what)

1. **Skeleton**: `requirements.txt`, `config.py`, `log_utils.py`, `common_schema.py`, `error_handlers.py`, `db_service.py`, health route/helper/schema, `main.py`. Expected: `/health` returns 200 with the DB running and 424 with it stopped.
2. **Database**: `models/base.py`, `models/user.py`, Alembic init and first migration.
3. **Auth**: auth schema, utils, helper, routes. Expected: register 201, duplicate 409, login, wrong password 401, `/me` 401 without a token.
4. **Each feature**: routes decided first, then model + migration, schemas, helper, routes.
5. README with setup and run steps.

## 3. Commands (Windows)

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
alembic upgrade head
uvicorn app.main:app --reload --reload-dir app
```

Pin versions in `requirements.txt` once the project works (`pip freeze` for the direct dependencies only). Keep test-only packages (pytest) in `requirements-dev.txt`.

## 4. Alembic with the async engine

```bat
alembic init -t async migrations
```

In `migrations/env.py`:

```python
from app.config import settings
from app.models import Base

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

and add `compare_type=True` to every `context.configure(...)` call. Remove the URL line from `alembic.ini`. Then `alembic revision --autogenerate -m "create users table"`, read the script, `alembic upgrade head`. Rules for reviewing and changing migrations: `sql-silk/references/migrations.md`.

## 5. MongoDB instead of SQL

- Use `mongodb_service.py`; drop `models/`, `db_service.py` and Alembic.
- `main.py` lifespan: `await MongoDBService.connect()` / `await MongoDBService.close()`.
- `error_handlers.py`: register `pymongo.errors.ConnectionFailure` instead of SQLAlchemy's `OperationalError` and pool timeout; drop the SQLAlchemy imports.
- `auth_utils.get_current_user`: look the user up with `users.find_one({"_id": ObjectId(claims["sub"])}, {"password_hash": 0})` after checking `ObjectId.is_valid`.
- Helpers use collections as shown in `mongodb-silk/references/queries-and-updates.md`; `health_helper` calls `MongoDBService.check_connection()`.
- Config fields: `mongodb_uri`, `mongodb_database`, `mongodb_max_pool_size`, `mongodb_min_pool_size` instead of the SQL ones.

## 6. .env.example additions

On top of `backend-silk/assets/env.example`:

```env
# Async driver: asyncpg (async psycopg doesn't run on Windows' ProactorEventLoop)
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/DB_NAME

# SQL connection pool (per worker)
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
```

MongoDB projects:

```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=app_db
MONGODB_MAX_POOL_SIZE=50
MONGODB_MIN_POOL_SIZE=0
```
