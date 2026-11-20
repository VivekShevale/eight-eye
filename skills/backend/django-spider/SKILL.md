---
name: django-spider
description: Builds and maintains Django REST Framework backends. Covers the config/ plus apps/domain-name/ layout with one app per business domain (never one app per model), custom email User with roles, thin DRF views calling helpers.py, serializers, role and object permissions, user-scoped querysets, transaction.atomic with select_for_update and history rows, SimpleJWT, a shared JSON error format through a custom exception handler, pagination, env-driven settings and logging, and tests with APITestCase, with a tested starter project (accounts plus a tickets domain with comments and history). Use this whenever the user creates a Django or DRF project, adds an app, model, serializer, view, URL or permission, sets up JWT, migrations or settings in Django, or debugs Django errors, even if they only paste a Django traceback. Apply together with backend-silk and sql-silk.
---

# Django Spider

Builds Django REST Framework projects on top of the shared standards. Load these too:

- `backend-silk`: layers, code rules, errors, logging, config, security, workflow. **Always.**
- `sql-silk`, especially `references/django-orm.md`: connections, transactions, queries, migrations in Django.

## Structure

```text
project/
├── manage.py
├── config/                    # project package
│   ├── settings.py            # everything from .env; no secrets in code
│   ├── logger.py              # LoggingConfig: LOG_LEVEL, LOG_TO_FILE
│   ├── urls.py                # api/v1/<domain>/ includes, health, JSON 404/500
│   └── wsgi.py / asgi.py
├── apps/
│   ├── common/                # shared code, not an installed app: error_handlers, pagination, health
│   ├── accounts/              # custom User, auth endpoints, role permissions
│   └── tickets/               # one business domain: Ticket + TicketComment + TicketHistory
│       ├── models.py          # every model of the domain
│       ├── serializers.py     # input validation and output shape (the schemas layer)
│       ├── helpers.py         # business rules (TicketHelper)
│       ├── views.py           # thin DRF views (the routes layer)
│       ├── urls.py
│       ├── permissions.py     # only when the app has its own permission rules
│       ├── admin.py
│       └── migrations/
├── tests/  (or apps/<domain>/tests.py)
├── .env  .env.example  .gitignore  requirements.txt  README.md
```

## One app per business domain, not per model

An app is a bounded part of the business that could be explained on its own: `accounts`, `tickets`, `billing`, `inventory`. Models that only make sense through another model belong in that model's app: comments, attachments, history and status logs of a ticket live in `apps/tickets/`, with URLs nested under `/api/v1/tickets/<id>/comments/`. A separate `comments` app for one model is a mistake the user made before; it causes cross-app imports of helpers, a URL file mounted at `api/v1/` that repeats `tickets/<id>/`, and migrations that depend on each other. Create a new app only when a new domain appears, and ask when unsure.

## Starting a new project

Starter project, tested end to end (4 test cases, about 60 assertions: auth, roles, ownership, transitions, history, comments, validation, failure paths): `assets/project/`. Copy map, build order and commands: `references/project-setup.md`. The custom `User` model must exist before the first `migrate`.

## Rules specific to Django

**Views (the routes layer)**
- DRF generics for plain list/retrieve (`ListAPIView`, `RetrieveAPIView` with `get_queryset` from the helper), `APIView` for actions. A view method: validate with a serializer → call one helper method → return `Response(OutputSerializer(obj).data, status=...)`. No queries, business rules or try/except in views.
- One view per URL; several HTTP methods on the same URL are methods of the same view (`patch` and `delete` together). Two views on one path make the second unreachable.
- `get_queryset` always starts from a user-scoped helper method, so other users' records are 404 automatically.

**Serializers (the schemas layer)**
- Separate input serializers (create, update, action payloads, list query params) from output serializers. Output fields are `read_only_fields = fields`.
- Query parameters are validated with a serializer too (`TicketListParamsSerializer`); invalid values are 400, not silently ignored.
- Validation that needs only the input (password policy with `password-validator`, choices, lengths) lives in the serializer; validation that needs the database (duplicates, ownership, state transitions) lives in the helper.
- DRF ignores unknown input fields; server-owned fields (`customer`, `status`, `role`) are never in input serializers, so they can't be set by clients.

**Helpers (business logic)**
- `apps/<domain>/helpers.py` with a class (`TicketHelper`) of static/class methods. Query helpers return querysets; action helpers take validated data and the acting user.
- Writes that belong together use `@transaction.atomic`; rows that are read then changed use `select_for_update()`. Never keep an atomic block open across email sending, LLM or external API calls (use `transaction.on_commit`).
- State machines are explicit maps (`ALLOWED_STATUS_TRANSITIONS`) checked before saving, with a history row written in the same transaction.
- Expected failures raise DRF exceptions: `NotFound`, `PermissionDenied` (403, role/action not allowed), `ValidationError` (400), `ConflictError` (409, in `apps/common/error_handlers.py`).

**Errors**
- `REST_FRAMEWORK["EXCEPTION_HANDLER"]` points at `apps.common.error_handlers.handle_exception`, which gives every DRF error the shared shape `{"status": "error", "message": ..., "details": [...]}`, maps database `OperationalError`/`InterfaceError` to 424, and turns anything unexpected into a logged 500.
- `handler404` / `handler500` in `config/urls.py` return the same JSON for unknown URLs and non-DRF crashes (active when `DEBUG=False`).
- Validation errors are 400 in DRF (not 422); page numbers out of range are 404 ("Invalid page.").

**Auth**
- Custom `User(AbstractUser)` with `username = None`, unique `email` as `USERNAME_FIELD`, a `Role` `TextChoices` field and a `UserManager`. `AUTH_USER_MODEL = "accounts.User"` before the first migration.
- SimpleJWT: `LoginView(TokenObtainPairView)` with a serializer whose `no_active_account` message is "Invalid email or password."; refresh via `TokenRefreshView`.
- `IsAuthenticated` is the default permission; public views (`register`, `login`, `health`) set `AllowAny` and empty `authentication_classes` explicitly. Never `AllowAny` on `/me/`.
- Role checks are `BasePermission` classes with a `message`; record visibility is enforced by scoped querysets.

**Settings and logging**
- `settings.py` reads `.env` once: `DJANGO_SECRET_KEY` (required, no insecure default), `DJANGO_DEBUG` (default false), `DJANGO_ALLOWED_HOSTS`, `CORS_ORIGINS`, `DB_*`, token lifetimes, `LOG_LEVEL`, `LOG_TO_FILE`. Only variables the code reads go in `.env.example`.
- PostgreSQL through `DB_ENGINE=django.db.backends.postgresql` and `DB_*` variables, with `CONN_MAX_AGE` and `CONN_HEALTH_CHECKS`; SQLite only as the local fallback, and `db.sqlite3` is never committed.
- Logging through `config/logger.py` (`LoggingConfig.build`), the same format and env flags as `LogUtils`; modules use `logger = logging.getLogger(__name__)`.

**URLs**
- `config/urls.py`: `path("api/v1/<domain>/", include("apps.<domain>.urls"))`; URL names unique (`ticket-list`, `ticket-detail`).
- Django paths end with `/`; clients call them with the slash (`/api/v1/tickets/`).

## Testing

Django's own runner with DRF's `APITestCase`: `python manage.py test`. Patterns: `references/testing.md`.

## Reference files

| File | Read when |
|---|---|
| `references/project-setup.md` | Creating a project, copying starter files, commands, PostgreSQL, .env |
| `references/apps-and-layers.md` | Adding an app, model, serializer, view, URL, permission; deciding where code goes |
| `references/testing.md` | Writing tests with APITestCase |
| `sql-silk/references/django-orm.md` | Transactions, query performance, migrations |

## Assets

`assets/project/` is a complete, runnable starter: `config/` (settings, logger, urls), `apps/common/` (exception handler, pagination, health), `apps/accounts/` (email User with roles, register/login/refresh/me), `apps/tickets/` (tickets with comments and history in one app, role permissions, status transitions). Migrations are not included: run `makemigrations accounts tickets` after copying. Rename or remove the tickets domain for the real project.
