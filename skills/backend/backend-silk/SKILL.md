---
name: backend-silk
description: Shared engineering standards for backend and API projects in Python (Flask, FastAPI, Django, FastMCP) and Node.js (Express). Covers project structure, the routes, helpers and services layering, class-based code rules, error handling and status codes, edge cases, logging, .env config, auth and data ownership, communication between repositories, git hygiene and tests. Use this whenever creating, extending, debugging, refactoring or reviewing any Python backend, REST API, MCP server or RAG backend, even if the user only asks for one endpoint, one fix or a commit message. The framework skills (flask-spider, fastapi-spider, django-spider, node-spider, mcp-spider) and database skills (sql-silk, mongodb-silk) build on this one.
---

# Backend Silk: shared backend standards

Act as a senior Python backend engineer who writes simple, production-grade code. The two failures this skill exists to prevent are **wrong structure** (logic in the wrong layer, files nobody needs) and **over-engineering** (abstractions before there is a working app). A third, quieter failure is just as costly: a change or refactor that silently drops behaviour that used to work.

## Companion skills

Naming: `*-spider` skills build a specific kind of project; `*-silk` skills are the shared standards every spider spins with. This skill holds the principles shared by every backend. Load the matching companions too:

| Situation | Also use |
|---|---|
| Flask / FastAPI / Django project | `flask-spider` / `fastapi-spider` / `django-spider` |
| Node.js / Express project | `node-spider` (the rules here apply; Python code samples are Python) |
| MCP server or MCP client | `mcp-spider` |
| PostgreSQL, MySQL, SQLite (SQLAlchemy, Django ORM) | `sql-silk` |
| MongoDB | `mongodb-silk` |
| LLM, embeddings, vector store, RAG | `rag-spider` |

Framework skills decide framework mechanics; this skill decides principles. If they seem to conflict, follow the framework skill for syntax and this skill for structure.

## Before changing code

1. **Read the real code first.** Check the folder structure, models, config and the file you are about to change. Never guess a field name, function signature, file name or import path; read it. (A guessed `date` instead of the real `expense_date` once broke schema, helper and response in one go.) When unsure how an installed library works, check its actual API instead of assuming.
2. **Decide the routes first.** For a feature, list each endpoint (method, path, request, response, status codes, auth) before implementing.
3. **Scope comes from the requirement.** Build what the problem statement needs. Extra endpoints, analytics, caching, rate limiting, re-ranking, cost tracking, download/search endpoints nobody asked for: mention in one line as "possible later", don't build.
4. **Preserve working behaviour.** When rewriting a function, list what it does now (filters, pagination, validation, logging, response fields) and make sure the new version still does all of it.

## Layers

```
routes -> helpers -> services -> database / external systems
            |            |
          utils        utils
```

| Folder | Owns | Must not contain |
|---|---|---|
| `routes/` (Flask blueprints, FastAPI routers, Django `views.py` + `urls.py`, MCP `tools/`) | URL, method, auth dependency/decorator, status code, response model, one call to a helper | Business logic, queries, validation code, try/except, logging |
| `helpers/` | Business logic for one feature, like a controller: validation beyond the schema, ownership checks, feature-specific queries and filters, orchestration of services, mapping expected failures to HTTP errors, building the response | Opening/closing DB sessions, commit/rollback, creating LLM or SDK clients |
| `services/` | One external system or infrastructure piece each: DB connection and generic CRUD (`db_service.py`), LLM, embeddings, vector store, PDF, email, another repo's API | Feature-specific business rules, HTTP knowledge (`HTTPException`, status codes), calls to helpers |
| `utils/` | Class-based code reused by several modules: `LogUtils`, `ErrorHandlers`, `AuthUtils`, pure converters | Code used by one feature only, external API calls |
| `schemas/` | Pydantic request/response models (Django: `serializers.py`) | DB models |
| `models/` | Persistence models | Business logic |
| `prompts/` | Prompt templates as code (only when an LLM is used) | Prompts in `.env` |
| `config.py` | One settings object loaded from `.env` | Logic |

Rules that follow from the table:

- **Direction is one way.** Routes call helpers, helpers call services. A service never calls a helper; a utility never calls a helper.
- **Database split.** The helper builds feature queries (filters, search, ownership); the DB service runs them and owns connection, session, commit and rollback. Details in `sql-silk` / `mongodb-silk`. With Django the ORM is the DB layer, so there is no `db_service`.
- **No pass-through layers.** If a helper only forwards to a service, delete the helper and call the service. Every file must earn its place.
- **Utils vs helpers.** Used in many places → `utils/`. Used by one feature → that feature's helper.
- **Create folders and files when a real need appears**, not up front. One function never justifies a new folder (`errors/`, `exceptions.py`, `core/`); add it to the existing class that fits.
- Naming: `<domain>_routes.py` (holding `<domain>_router`, or `<domain>_bp` in Flask), `<domain>_helper.py` → `XHelper`, `<domain>_service.py` → `XService`, `<domain>_schema.py`, `<domain>_utils.py` → `XUtils`, `<name>_prompt.py` → `NAME_PROMPT`. A class name always matches its folder (a `class ExpenseService` inside `helpers/` is wrong).

Full folder roles and starting trees: `references/architecture.md`.

## Code rules

1. **Class-based modules.** Helpers, services and utils are classes. Use `@staticmethod`/`@classmethod` for stateless code and instances only when the class holds a dependency (e.g. an injected session or client). Route files and Django `urls.py` stay module-level. Don't force inheritance, abstract base classes or interfaces without two real implementations.
2. **Functions stay around 40–50 lines.** Split a long function into meaningful methods of the same class (e.g. `list_expenses` → `parse_filter_parameters` + `apply_expense_filters`), not arbitrary chunks.
3. **No function names starting with `_`. No functions defined inside functions.** Register handlers with explicit calls such as `app.add_exception_handler(...)` instead of nested decorated functions.
4. **All imports at the top of the file**, grouped stdlib → third-party → `app.*`. Fix circular imports by moving code to the right module, not by importing inside functions. The one accepted exception is Flask blueprint imports inside `create_app()`.
5. **Use established libraries instead of hand-written logic**: `password-validator`, `email-validator`/`EmailStr`, PyJWT, bcrypt, LangChain loaders and splitters, `httpx`.
6. **Validate once.** If the Pydantic schema already enforces a rule, don't re-check it in the helper.
7. **Don't compute the same thing twice in one request, and fail fast.** Do cheap checks before expensive ones (duplicate-email check before bcrypt hashing).
8. **No hardcoded configuration**: URLs, model names, limits, top_k, temperature and secrets come from `config.py`.
9. **No dead code**: unused functions, unused imports, empty placeholder files and `startapp` leftovers get removed.
10. **Type hints and a one-line docstring** on every class and public method. Comments only where the reason isn't obvious.
11. **Never swallow exceptions.** Catch specific exceptions where you can act on them; let the rest reach the global handler.

## Over-engineering check

Before adding a file, class, layer, dependency or pattern, ask: does the current requirement need it, and does something existing already do it? These were all built and then removed:

- pydantic-settings or validation frameworks before the app runs (a frozen dataclass config is enough)
- a new exception module or class for one error
- helpers that only call a service
- RS256 key pairs between two services you own (an HS256 shared secret is enough)
- stored derived values (`total_tokens` when input + output exist)
- two collections or tables where one with an embedded list works
- long prompts and long tool descriptions

When several designs work, choose the simplest one that is still production-safe.

## Request and response schemas (summary)

- Every endpoint validates its body and query parameters with a request schema that rejects unknown and server-owned fields; code after validation uses only the validated object.
- Every successful response is built from a response schema: the resource itself (`XResponse`), a list `{"items", "page", "page_size", "total", "total_pages"}`, or an action result schema (`TokenResponse`). No envelope, no object literals assembled in the handler.
- Status codes carry success and failure: 200 read/update, 201 create, 204 delete with no body, errors with `ErrorResponse`. Never a failure with 200.

Full contract and where schemas live per framework: `references/api-design.md`.

## Errors (summary)

- Every error response has one shape, from `assets/common_schema.py`:
  `{"status": "error", "message": "...", "details": [{"field": "...", "message": "..."}]}` (`details` only when there are field errors)
- Services raise plain or library exceptions; helpers raise HTTP errors for expected cases; one `ErrorHandlers` class in `utils/error_handlers.py` maps dependency errors and catches everything else as a 500.
- Status codes: 400 bad input, 401 unauthenticated, 404 missing **or another user's record**, 409 duplicate, 413 too large, 422 schema validation, 424 our own dependency down (database, vector store), 429 upstream rate limit, 502 upstream returned an error, 503 another service unreachable, 504 upstream timeout, 500 unexpected. Never 200 for a failure.
- Users see a short safe message, never a traceback, host, connection string or key.

Edge-case checklist and handler patterns: `references/errors-and-edge-cases.md`. Calls between repositories: `references/cross-repo-communication.md`.

## Logging (summary)

One `LogUtils` class (`assets/log_utils.py`) configured once at startup from `LOG_LEVEL` and `LOG_TO_FILE` in `.env`; every other module only does `logger = LogUtils.get_logger(__name__)`. Format `%(asctime)s | %(levelname)s | %(name)s | %(message)s`, messages as `Event | key=value`, no secrets or personal data, each failure logged once. Details: `references/logging.md`.

## Config and security (summary)

- `config.py` with a frozen dataclass loaded from `.env` (`assets/config.py`); `.env.example` committed with placeholders and comments (`assets/env.example`), `.env` never committed (`assets/gitignore`).
- Passwords: `password-validator` policy at registration only, bcrypt/werkzeug hashing, generic "Invalid email or password." at login.
- JWT: secret from `.env`, user id taken only from the verified token, never from the request body.
- Every query is scoped to the current user; other users' records return 404.

Details: `references/security.md`. API conventions (methods, pagination, filtering, search parameters): `references/api-design.md`.

## Git and tests (summary)

- Never committed: `.env`, keys, credentials, uploads, vector data, local databases, logs, virtual environments, generated reports. Migrations are committed with the model change that produced them.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `refactor:`, `chore:`, `test:`, `docs:`, `perf:`), one concern per commit, one commit per repository.
- Tests cover critical paths: auth, ownership between users, validation, error responses, dependency failures (mocked). External services (LLMs, other repos) are mocked.
- **Evaluations** (golden datasets, eval scripts, reports) exist only when explicitly requested; see `rag-spider` / `mcp-spider`.

Details: `references/git-and-testing.md`.

## Code checklist

- [ ] Layers respected; no pass-through file; class names match folders
- [ ] No leading-underscore or nested functions; imports at top; functions ≤ ~50 lines
- [ ] Existing behaviour preserved (filters, pagination, validation, response fields)
- [ ] Every endpoint has a request schema and a response schema; no ad-hoc response objects
- [ ] Edge cases from `references/errors-and-edge-cases.md` handled with correct status codes
- [ ] New settings in `config.py` and `.env.example`; nothing hardcoded; no secrets in code or logs
- [ ] Logging added where it fits, at the right level
- [ ] No unused imports or dead code left behind

## Reference files (read only when needed)

| File | Read when |
|---|---|
| `references/architecture.md` | Creating a project, adding a feature folder, unsure where code belongs |
| `references/errors-and-edge-cases.md` | Writing endpoints, error handlers, or reviewing failure paths |
| `references/cross-repo-communication.md` | One service calls another repo, MCP server, or external API |
| `references/logging.md` | Setting up or reviewing logging |
| `references/security.md` | Auth, passwords, JWT, uploads, secrets, CORS |
| `references/api-design.md` | Designing endpoints, request/response schemas, pagination, filters, search |
| `references/git-and-testing.md` | Commits, PR descriptions, what never gets committed, tests, debugging approach |

## Asset files (copy into the project and adapt)

Copy templates selectively: keep only the parts this project uses now (sections of `.gitignore`, `.env.example` keys, config fields). Leftover lines for features the project doesn't have are clutter and mislead the next reader.

| File | Becomes |
|---|---|
| `assets/log_utils.py` | `app/utils/log_utils.py` |
| `assets/common_schema.py` | `app/schemas/common_schema.py` |
| `assets/config.py` | `app/config.py` |
| `assets/env.example` | `.env.example` |
| `assets/gitignore` | `.gitignore` (the "Always" section plus only the marked sections that apply) |
