# Project Setup

## Contents
1. Copy map
2. Build order
3. Commands (Windows)
4. PostgreSQL
5. .env.example

## 1. Copy map

| Project file | Source (`django-spider/assets/project/`) |
|---|---|
| `manage.py`, `requirements.txt` | root |
| `config/settings.py`, `logger.py`, `urls.py`, `wsgi.py`, `asgi.py`, `__init__.py` | `config/` |
| `apps/__init__.py`, `apps/common/*` | shared error handler, pagination, health view/helper |
| `apps/accounts/*` | custom User, serializers, helpers, views, urls, permissions, admin |
| `apps/tickets/*` | example domain (tickets + comments + history in one app) |
| `.gitignore` | `backend-silk/assets/gitignore` ("Always" section plus `db.sqlite3`, and other sections only if used) |

`INSTALLED_APPS` and `config/urls.py` list only the apps that exist. `apps/common/` is a plain package, not an installed app (it has no models).

## 2. Build order (what depends on what)

1. **Skeleton**: requirements, `config/`, `apps/common/`, `apps/accounts/models.py` with the custom User (it must exist before any `migrate`), `makemigrations accounts`, `migrate`. Expected: `/health/` 200.
2. **Auth**: accounts serializers, helper, views, urls. Expected: register 201, duplicate 409, weak password 400, login, wrong password 401, `/me/` 401 without a token.
3. **Each domain**: endpoints decided first, then models (all models of the domain in its app), `makemigrations <app>`, read the migration, `migrate`, serializers, helper, views, urls.
4. README with setup and run steps.

## 3. Commands (Windows)

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(50))"
python manage.py makemigrations accounts tickets
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Other common commands:

| Task | Command |
|---|---|
| New app | `mkdir apps\billing` then `python manage.py startapp billing apps\billing`; set `name = "apps.billing"` in `apps.py`; remove generated placeholders (`tests.py` stub, `# Create your views here.`) |
| Migration for one app | `python manage.py makemigrations billing` |
| SQL of a migration | `python manage.py sqlmigrate billing 0001` |
| Migration state | `python manage.py showmigrations billing` |
| Shell with models | `python manage.py shell` |
| Tests | `python manage.py test` |
| Checks before deploy | `python manage.py check --deploy` |

## 4. PostgreSQL

Set `DB_ENGINE=django.db.backends.postgresql` and the `DB_*` variables; `psycopg[binary]` is already in requirements. Without `DB_ENGINE` the project falls back to `db.sqlite3` for local work. `CONN_MAX_AGE=60` reuses connections between requests; keep `workers × 1` connection per thread below PostgreSQL's `max_connections`.

## 5. .env.example

```env
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(50))"
DJANGO_SECRET_KEY=
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
CORS_ORIGINS=http://localhost:5500

# Leave DB_ENGINE empty to use SQLite locally
DB_ENGINE=django.db.backends.postgresql
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
DB_CONN_MAX_AGE=60

ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=1

# DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO
# true writes logs/app.log (rotating, 5 MB x 5)
LOG_TO_FILE=false
```

Every key here must be read by `settings.py` under exactly this name; a renamed variable (`MAIL_HOST` in `.env.example` but `EMAIL_HOST` in settings) silently falls back to defaults.
