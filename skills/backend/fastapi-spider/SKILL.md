---
name: fastapi-spider
description: Builds and maintains FastAPI backends. Covers project setup, the routes, helpers and services structure, APIRouter conventions, Depends-based auth, Pydantic request, response and query models, lifespan startup, async rules (asyncio.to_thread, shared clients), central exception handlers, uvicorn on Windows, and pytest with TestClient, with a tested starter project (auth plus an example CRUD feature). Use this whenever the user creates a FastAPI app, adds or changes an endpoint, router, schema, dependency or middleware, wires a database, LLM or MCP client into FastAPI, or debugs FastAPI errors (422s, 307 redirects, blocked event loop, uvicorn reload loops), even if they only paste a FastAPI traceback. Apply together with backend-silk and sql-silk or mongodb-silk.
---

# FastAPI Spider

Builds FastAPI projects on top of the shared standards. Load these too:

- `backend-silk`: layers, code rules, errors, logging, config, security, workflow. **Always.**
- `sql-silk` (PostgreSQL/MySQL/SQLite) or `mongodb-silk` (MongoDB): the database layer.
- `rag-spider` for LLM/RAG features, `mcp-spider` for MCP servers or clients.

## Structure

```text
project/
├── app/
│   ├── main.py            # assembly only: logging, lifespan, CORS, handlers, routers
│   ├── config.py          # frozen dataclass settings from .env
│   ├── routes/            # <domain>_routes.py -> <domain>_router
│   ├── helpers/           # <domain>_helper.py -> XHelper (business logic)
│   ├── services/          # db_service.py / mongodb_service.py, llm_service.py, ...
│   ├── schemas/           # <domain>_schema.py, common_schema.py (ErrorResponse)
│   ├── models/            # base.py + one file per table (SQL only)
│   ├── utils/             # log_utils.py, error_handlers.py, auth_utils.py
│   └── prompts/           # only with an LLM
├── migrations/            # Alembic (SQL only)
├── tests/
├── .env  .env.example  .gitignore  requirements.txt  README.md
```

Every folder is a package (`__init__.py`). Create folders and files when their first feature needs them.

## Starting a new project

Starter project (tested end to end: 35 checks on auth, CRUD, filters, ownership, validation and failure paths): `assets/project/`. Its shared files come from the silk skills; the copy map and build order are in `references/project-setup.md`.

## Rules specific to FastAPI

**Routes**
- `<domain>_router = APIRouter(prefix="/api/v1/<plural>", tags=["<Domain>"])`, defined at module level. Never `_bp` names or Flask habits.
- Every route declares `response_model` and its status code (`status.HTTP_201_CREATED` for create, `HTTP_204_NO_CONTENT` for delete returning nothing).
- The body is one call: `return await XHelper.method(...)`. No try/except, logging, queries or `JSONResponse` in routes.
- Collection paths without a trailing slash (`@router.get("")` → `/api/v1/expenses`) and the client calls the same form; a mismatch causes a 307 redirect.

**Dependencies and auth**
- Auth is a dependency parameter: `current_user: dict = Depends(AuthUtils.get_current_user)`. Keep it as a parameter whenever the route needs the user (almost always); `dependencies=[Depends(...)]` on the decorator or router discards the value and only suits pure checks (admin-only, rate limit).
- FastAPI runs a dependency once per request even if it's declared at router level and as a parameter.
- Auth never goes in middleware: middleware can't hand `current_user` to the route and would also run on public routes like `/login` and `/health`.
- No request-scoped DB session dependency (`Depends(get_db)`); DBService opens its own short sessions (see `sql-silk`).

**Schemas**
- Request bodies: Pydantic models with `ConfigDict(extra="forbid")`, `str_strip_whitespace=True` where useful, `Field` constraints. Optional fields need `= None` or they're still required.
- Query parameters for lists: one Pydantic model, `params: Annotated[XListParams, Query()]`, with defaults, bounds and cross-field checks (`model_validator`). Never parse `request.query_params` by hand.
- Separate `XCreateRequest`, `XUpdateRequest` (all optional), `XResponse` (`from_attributes=True` for ORM objects), `XListResponse`.
- A field named `date` shadows the type: `from datetime import date as DateType`.
- File uploads: `file: UploadFile = File(...)`, no Pydantic model.
- FastAPI already validates bodies and serializes `response_model`: don't port Flask's `RequestUtils.parse_schema` / `ResponseUtils` / `jsonify`.

**Async**
- Routes are `async def` and await async services (async SQLAlchemy engine with `postgresql+asyncpg://`, `AsyncMongoClient`, `httpx.AsyncClient`). Async psycopg fails on Windows, where uvicorn uses the ProactorEventLoop.
- Blocking work inside `async def` freezes every request: wrap it at the call site with `await asyncio.to_thread(...)` (bcrypt, PDF parsing, embedding models, ChromaDB, sync SDKs, file I/O on large files).
- Long-lived clients are created once: lifespan (`DBService.connect()`, `MongoDBService.connect()`) or `@staticmethod @lru_cache(maxsize=1)` getters for LLM/embedding/vector clients.

**Errors**
- Helpers raise `HTTPException(status_code=..., detail="...")`; `utils/error_handlers.py` (`assets/project/app/utils/error_handlers.py`) turns everything into the shared `ErrorResponse` and is registered once with `ErrorHandlers.register_handlers(app)`.
- Handlers are static methods registered with `app.add_exception_handler`, never nested `@app.exception_handler` functions.
- Add new dependency handlers (Groq `APIStatusError`, MCP connection errors) as methods of the same class.

**main.py**
- One `app = FastAPI(title=settings.app_name, lifespan=lifespan)`. `LogUtils.configure_logging()` runs at import, before the app is created; `lifespan` is the one module-level function FastAPI requires here.
- CORS with origins from `CORS_ORIGINS`, never `"*"` with credentials.
- Nothing else: no routes, handlers or connection code defined in `main.py`.

**Running**
- `uvicorn app.main:app --reload --reload-dir app` (Windows: after `venv\Scripts\activate`). `--reload-dir app` stops restarts when logs, uploads, eval scripts or vector data change.
- Swagger UI at `/docs` for manual checks. Production: no `--reload`, `--workers N` (each worker has its own DB pool, see `sql-silk`).

## Testing

pytest with `TestClient(app, raise_server_exceptions=False)` used as a context manager (runs the lifespan), a separate test database through env vars, and mocked LLM/external services. Patterns: `references/testing.md`.

## Reference files

| File | Read when |
|---|---|
| `references/project-setup.md` | Creating a project, copying starter files, build order, Alembic setup, requirements |
| `references/routes-and-schemas.md` | Writing routers, dependencies, query/body/response models, uploads, status codes |
| `references/async-and-clients.md` | Blocking calls, shared clients, lifespan, background work, workers |
| `references/testing.md` | Writing pytest tests for routes, auth, ownership and failure paths |

## Assets

`assets/project/` is a complete, runnable starter (auth with register/login/me, an example `expenses` feature with filters and pagination, health check, error handlers). Copy the files the project needs; rename or remove the example feature for the real domain.
