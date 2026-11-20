# Async and Shared Clients

## Why it matters

uvicorn runs `async def` routes on one event loop per worker. While a coroutine runs blocking code (CPU work or a sync network/disk call), no other request on that worker makes progress. One user uploading a PDF that takes 3 s to embed would stall everybody for 3 s.

## Blocking calls and what to do

| Work | In async code |
|---|---|
| SQL queries | Async SQLAlchemy engine via DBService |
| MongoDB | `AsyncMongoClient` |
| HTTP calls | `httpx.AsyncClient` (never `requests`) |
| bcrypt hash/check | `await asyncio.to_thread(bcrypt.hashpw, ...)` (done in `AuthUtils`) |
| PDF parsing, text splitting of big documents | `await asyncio.to_thread(PDFService.extract_pages, path)` |
| sentence-transformers / local embedding models | `await asyncio.to_thread(EmbeddingService.embed_texts, texts)` |
| ChromaDB (sync client) | `await asyncio.to_thread(VectorStoreService.add_chunks, ...)` |
| LangChain chat models | `await model.ainvoke(...)` (async API) |
| Reading/writing large files | `asyncio.to_thread` or `aiofiles` |

Wrap at the call site in the helper or async service; keep the sync service methods themselves sync. Converting every route to plain `def` is not the fix: it gives up async I/O everywhere else.

## Shared clients

Create each expensive client once per process:

```python
class LLMService:
    """Chat model access."""

    @staticmethod
    @lru_cache(maxsize=1)
    def get_model() -> ChatGroq:
        """Create the chat model once and reuse it."""
        return ChatGroq(model=settings.groq_model, temperature=settings.llm_temperature, api_key=settings.groq_api_key)
```

- Database clients: `connect()` in the lifespan, `close()` at shutdown.
- LLM, embedding and vector-store clients: `lru_cache(maxsize=1)` getters, created on first use.
- A config change for a cached client needs a restart; say so when changing `.env`.

## Lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared clients at startup and close them at shutdown."""
    DBService.connect()
    yield
    await DBService.close()
```

The lifespan never crashes the app because a dependency is down; the dependency's endpoints return 424 instead (see `backend-silk`).

## Background work

- Short follow-up work that doesn't affect the response (sending an email, updating a summary): `BackgroundTasks` parameter, `background_tasks.add_task(Helper.method, ...)`. It runs after the response in the same worker, so it must handle and log its own errors.
- Long or must-not-be-lost work: a real queue is a separate decision; mention it, don't build it unasked.

## Workers

- `uvicorn app.main:app --workers 4` (or gunicorn with uvicorn workers) in production.
- Each worker has its own DB pool and its own in-memory state: in-memory caches, sessions or rate-limit counters are not shared between workers.
