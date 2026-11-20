---
name: flask-spider
description: Builds and maintains Flask REST APIs. Covers the create_app factory, extensions.py, blueprints, thin routes calling class-based helpers, Pydantic request and query validation (RequestUtils), Flask-SQLAlchemy with the short-session DBService, Flask-Migrate, Flask-JWT-Extended auth with shared error responses, central error handlers, logging, and pytest with the Flask test client, with a tested starter project (auth plus an example CRUD feature). Use this whenever the user creates a Flask app, adds or changes a blueprint, route, schema or model, sets up JWT or migrations in Flask, or debugs Flask errors (circular imports, 308 redirects, migration drift, AmbiguousForeignKeysError), even if they only paste a Flask traceback. Apply together with backend-silk and sql-silk.
---

# Flask Spider

Builds Flask projects on top of the shared standards. Load these too:

- `backend-silk`: layers, code rules, errors, logging, config, security, workflow. **Always.**
- `sql-silk`: models, DBService rules, migrations, queries (Flask projects here use PostgreSQL via SQLAlchemy). `mongodb-silk` if a Flask app uses MongoDB.

## Structure

```text
project/
├── run.py                 # app = create_app(); `flask --app run.py run`
├── app/
│   ├── __init__.py        # create_app(): config, logging, extensions, handlers, blueprints
│   ├── config.py          # frozen dataclass settings from .env
│   ├── extensions.py      # db, migrate, jwt created without an app
│   ├── routes/            # <domain>_routes.py -> <domain>_bp blueprints
│   ├── helpers/           # <domain>_helper.py -> XHelper (business logic)
│   ├── services/          # db_service.py (+ llm/other integrations)
│   ├── schemas/           # Pydantic: <domain>_schema.py, common_schema.py
│   ├── models/            # base.py + one file per table; __init__.py stays empty
│   └── utils/             # log_utils, error_handlers, auth_utils, request_utils
├── migrations/            # Flask-Migrate, committed
├── tests/
├── .env  .env.example  .gitignore  requirements.txt  README.md
```

## Starting a new project

Starter project, tested end to end (35 checks on auth, CRUD, filters, ownership, validation and failure paths, plus a real Flask-Migrate migration): `assets/project/`. Copy map and build order: `references/project-setup.md`.

## Rules specific to Flask

**App factory**
- `create_app()` only assembles: `LogUtils.configure_logging()`, `app.config.update(...)` from `settings`, `init_app` for each extension, `ErrorHandlers.register_handlers(app, jwt)`, `register_blueprint(...)`. No routes, error handlers or business code defined inside it.
- Extensions are created in `extensions.py` without an app and bound with `init_app`, so any module can import `db` without circular imports.
- All imports at the top of `app/__init__.py`. Blueprint imports inside `create_app()` are the accepted fallback only if a real circular import appears.
- `app/models/__init__.py` stays empty: `extensions.py` imports `models/base.py`, so importing models there loops back. `app/__init__.py` imports each model module once (`from app.models import expense, user`) so Flask-Migrate sees every table.

**Blueprints and routes**
- `<domain>_bp = Blueprint("<domain>", __name__, url_prefix="/api/v1/<plural>")` at module level.
- A route does three things on one line: validate input with `RequestUtils`, get the user with `AuthUtils`, call the helper: `return ExpenseHelper.create_expense(RequestUtils.parse_body(ExpenseCreateRequest), AuthUtils.get_current_user_id())`.
- Protected routes: `@jwt_required()` under the route decorator.
- Collection rules are `""` (`/api/v1/expenses`, no trailing slash); `"/"` makes Flask answer `/api/v1/expenses` with a 308 redirect.
- Path converters type the id: `/<int:expense_id>` (a non-integer id is a 404, not a crash).

**Requests and responses**
- Flask doesn't validate input: `RequestUtils.parse_body(Schema)` / `parse_query(Schema)` validate with Pydantic and raise `RequestValidationError` (400 with field details). Never read `request.get_json()` or `request.args` in helpers; helpers receive validated schema objects, which keeps them testable without a request.
- Helpers return `(body_dict, status)`: `ExpenseResponse.model_validate(expense).model_dump(mode="json"), 201`; delete returns `"", 204`. No `jsonify`.
- Expected errors: raise werkzeug exceptions in helpers (`NotFound("Expense not found.")`, `Conflict(...)`, `BadRequest(...)`, `Unauthorized(...)`, `Forbidden(...)`). `ErrorHandlers` turns them into the shared `ErrorResponse`.

**Auth (Flask-JWT-Extended)**
- Token identity is the user id as a string; `jwt.user_lookup_loader(AuthUtils.load_user)` rejects tokens of deleted users.
- `AuthUtils.get_current_user_id()` reads `current_user`; never accept user ids from the body.
- Flask-JWT-Extended answers auth failures itself with `{"msg": ...}`. The starter registers `unauthorized_loader`, `invalid_token_loader`, `expired_token_loader` and `user_lookup_error_loader` as `ErrorHandlers` static methods so those 401s use the shared shape and the `WWW-Authenticate: Bearer` header.
- Passwords: werkzeug `generate_password_hash` / `check_password_hash`; policy with `password-validator` in the register schema (max 100).

**Database**
- Flask-SQLAlchemy owns the engine and pool (`SQLALCHEMY_ENGINE_OPTIONS` from `DBService.get_pool_options()`); `db = SQLAlchemy(model_class=Base)` with the naming-convention `Base` from `sql-silk`; models subclass `db.Model` plus the mixins.
- All queries go through the Flask `DBService` (`assets/project/app/services/db_service.py`): short sessions on `db.engine`. Don't use the request-scoped `db.session` or legacy `Model.query`.
- `DATABASE_URL` is required at startup (Flask-SQLAlchemy needs it); an unreachable server still gives 424 per request.
- Migrations: `flask --app run.py db migrate -m "..."`, read the script, `flask --app run.py db upgrade`. SQLite uses batch mode automatically (`render_as_batch`).

**Logging**
- Copy `backend-silk/assets/log_utils.py` and set `SERVER_LOGGERS = ("werkzeug",)`. Flask's `app.logger` then writes through the same handlers.

**Running**
- `flask --app run.py run --debug` locally (Windows: after `venv\Scripts\activate`). Production: a WSGI server (`waitress-serve --call app:create_app` on Windows, gunicorn on Linux), never the debug server.

## Testing

pytest with `create_app()` and `app.test_client()`, a separate test database through env vars, `db.create_all()` inside an app context for the throwaway test DB. Patterns: `references/testing.md`.

## Reference files

| File | Read when |
|---|---|
| `references/project-setup.md` | Creating a project, copying starter files, build order, commands, Flask-Migrate setup |
| `references/routes-and-requests.md` | Writing blueprints, request validation, responses, JWT, CORS, uploads |
| `references/testing.md` | Writing pytest tests with the Flask test client |

## Assets

`assets/project/` is a complete, runnable starter (factory, extensions, config, Flask DBService, error handlers with JWT loaders, request utils, auth with register/login/me, an example `expenses` feature, health check). Copy the files the project needs; rename or remove the example feature for the real domain.
