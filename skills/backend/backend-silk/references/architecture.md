# Architecture

## Contents
1. Folder roles in detail
2. Starting trees
3. What each layer looks like
4. Config, startup and dependencies
5. Where does this code go? (decision guide)
6. Decisions already made

## 1. Folder roles in detail

**routes/** answers HTTP. A handler is one line of real work: take the validated input and the current user, call one helper method, return its result. Auth is a decorator (`@jwt_required()`) or a dependency (`Depends(AuthUtils.get_current_user)`). Routes are defined at module level, never inside functions or classes (except FastMCP tool classes, see `mcp-spider`).

**helpers/** hold the business logic of one feature, the way a controller does in Node/Express. A helper:
- checks business rules the schema can't (duplicate email, allowed status transition, ownership)
- builds feature-specific queries (filters, search, sort, pagination)
- calls services (DB service, LLM, vector store, other repo clients)
- converts expected failures to HTTP errors (400/404/409/413)
- logs business events (created, updated, deleted, rejected)
- builds the response schema

**services/** wrap one external system each. The DB service owns the connection/session lifecycle and generic CRUD; `llm_service` owns the LLM client; `vectorstore_service` owns the vector collection; `<repo>_client` or `mcp_client` owns calls to another repo. Services raise plain or library exceptions (`ValueError`, `PyMongoError`, `httpx.HTTPError`) and know nothing about HTTP status codes. Expensive clients are created once (startup, lifespan or `@lru_cache(maxsize=1)`), never per request.

**utils/** hold class-based code used by several modules: `LogUtils`, `ErrorHandlers`, `AuthUtils` (current-user dependency, token helpers), `ChatUtils`, pure converters (Markdown → Google Docs). Utils do no external API calls; a pure transformation that several features need lives here.

**schemas/** hold Pydantic models: `XCreateRequest`, `XUpdateRequest` (all fields optional), `XResponse`, list responses, and the shared `ErrorResponse` in `common_schema.py`.

**models/** hold persistence models (SQLAlchemy tables, Django models, or Mongo document shapes when the project uses them).

**prompts/** hold LLM prompt templates as Python constants, added only when an LLM is used.

Optional top-level folders, added only when needed: `migrations/` (SQL), `scripts/` (runnable tools such as a CLI chat, run with `python -m scripts.chat_cli`, needs `scripts/__init__.py`), `tests/`, `eval/` (only when evaluations are requested), `frontend/` (one minimal HTML file unless asked otherwise), runtime folders `logs/`, `uploads/`, `chroma_data/` (gitignored).

## 2. Starting trees

Start small. This is the full shape a project can grow into; create a file only when its feature starts.

```text
project/
├── app/
│   ├── routes/          # <domain>_routes.py
│   ├── helpers/         # <domain>_helper.py
│   ├── services/        # db_service.py, llm_service.py, ...
│   ├── schemas/         # <domain>_schema.py, common_schema.py
│   ├── models/          # SQL / document models
│   ├── utils/           # log_utils.py, error_handlers.py, auth_utils.py
│   ├── prompts/         # only with an LLM
│   ├── config.py
│   └── main.py          # FastAPI; Flask uses app/__init__.py + run.py
├── migrations/          # SQL only
├── tests/
├── .env  .env.example  .gitignore  requirements.txt  README.md
```

Django uses `config/` + `apps/<domain>/` instead (see `django-spider`). FastMCP servers use `tools/` in place of `routes/` (see `mcp-spider`).


## 3. What each layer looks like

Route (FastAPI shown; Flask and Django differ only in syntax):

```python
@expense_router.post("/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseCreateRequest, current_user: dict = Depends(AuthUtils.get_current_user)):
    return await ExpenseHelper.create_expense(payload, current_user["user_id"])
```

Helper:

```python
class ExpenseHelper:
    """Business logic for expenses."""

    @staticmethod
    async def create_expense(payload: ExpenseCreateRequest, user_id: int) -> ExpenseResponse:
        """Create an expense owned by the current user."""
        expense = Expense(**payload.model_dump(), user_id=user_id, created_by=user_id, updated_by=user_id)
        expense = await DBService.create(expense)
        logger.info("Expense created | expense_id=%s | user_id=%s", expense.id, user_id)
        return ExpenseResponse.model_validate(expense)
```

Service: see `sql-silk` (`DBService`) and `mongodb-silk` (`MongoDBService`).

## 4. Config, startup and dependencies

- `config.py` loads `.env` once (`load_dotenv()` in that one module only) into a frozen dataclass and exposes a module-level `settings`. Template: `assets/config.py`.
- Validate required secrets at startup and fail fast with a clear message. Do **not** crash the app because a database is unreachable or its URI is missing; the app starts and DB-dependent endpoints return 424 (the user's explicit choice).
- `main.py` / `create_app()` only assembles: configure logging, create the app, lifespan (connect/close clients), register error handlers, include routers, `/health`. No handlers, routes or connection code defined inside it.
- Long-lived clients are created once per process and closed at shutdown. Never open a client per request or per query.
- Constructors do no I/O (no index creation, no network calls in `__init__`).

## 5. Where does this code go?

| Code | Place |
|---|---|
| Parse and validate request body | Schema (Pydantic / serializer) |
| "Email already registered", "status can't go from CLOSED to OPEN" | Helper |
| `select(Expense).where(...)` filters for one feature | Helper |
| `session.commit()` / `rollback()` / opening sessions, Mongo client | DB service |
| Calling Groq / OpenAI / Chroma / Google API / another repo | Service |
| Current user from JWT | `AuthUtils` in utils |
| Error → JSON response mapping | `ErrorHandlers` in utils |
| Converting Markdown to another format, used by two features | Utils class |
| Token usage logging needed by chat and RAG | Utils class (e.g. `ChatUtils`) |
| Prompt text | `prompts/<name>_prompt.py` |
| Tunable number (top_k, chunk size, page size limit) | `.env` → `config.py` |

## 6. Decisions already made (don't re-propose the rejected option)

- Config: frozen dataclass + `os.getenv` (pydantic-settings rejected as over-engineering for these projects).
- Error body: `{"status", "message", "details"}` everywhere.
- Dependency down: 424 for our own DB/vector store; 503 when another service can't be reached.
- Helpers own feature queries; DB service owns sessions and generic CRUD.
- Request/response utils from Flask are not ported to FastAPI (FastAPI validates and serializes itself).
- Middleware only for cross-cutting concerns every request needs (CORS, request timing); auth and per-route checks use dependencies/decorators.
- JWT between your own services: HS256 shared secret with issuer and audience checks.
- Internal layers call each other directly in Python; only external clients (frontend, CLI, other repos) use HTTP.
