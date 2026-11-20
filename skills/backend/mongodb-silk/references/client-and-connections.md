# Client and Connections

## Contents
1. What happens when
2. Client options
3. Startup, failure and health
4. Sync vs async
5. FastAPI, Flask and FastMCP wiring
6. Why not connect per request

## 1. What happens when

```text
App startup (lifespan -> MongoDBService.connect())
  AsyncMongoClient(...) created          pool exists, empty (minPoolSize=0)
  ping + create_indexes                  first connections opened

Each request
  Depends(AuthUtils.get_current_user)
    users.find_one(...)                  borrow 1 connection (~2 ms), return it
  route -> helper
    chats.find(...), messages.insert_one(...)   each borrows and returns
  LLM call (seconds)                     no connection held

App shutdown
  client.close()                         all pooled connections closed
```

`maxPoolSize=50` means 50 operations running at the same instant per worker, not 50 users. Operation 51 waits for a free connection (up to `waitQueueTimeoutMS`) instead of failing immediately.

## 2. Client options

```python
AsyncMongoClient(
    settings.mongodb_uri,
    maxPoolSize=settings.mongodb_max_pool_size,   # 50
    minPoolSize=settings.mongodb_min_pool_size,   # 0; raise to keep warm connections
    maxIdleTimeMS=60000,             # drop idle connections
    serverSelectionTimeoutMS=5000,   # how long to wait for a usable server
    connectTimeoutMS=5000,
    socketTimeoutMS=20000,           # a single operation can't hang forever
    waitQueueTimeoutMS=5000,         # fail instead of waiting forever when the pool is full
    retryWrites=True,
    tz_aware=True,                   # datetimes come back with tzinfo=UTC
)
```

Sizing: `workers × maxPoolSize` below the server/Atlas connection limit (e.g. 4 workers × 50 = 200).

## 3. Startup, failure and health

Rule: the app must start even if MongoDB is down or misconfigured, and DB-dependent requests return 424.

- `connect()`:
  - `MONGODB_URI` missing → log ERROR, no client; `get_database()` raises `ConnectionError("Database is not configured.")` → 424.
  - Server unreachable → log ERROR with `error_type`, keep the client (PyMongo reconnects by itself), mark indexes as not ready.
- `get_database()` creates the indexes on the first call after MongoDB becomes reachable (create_index is idempotent), so unique constraints are never silently missing. After that it just returns the database: no ping.
- Requests while MongoDB is down fail after `serverSelectionTimeoutMS` with `ServerSelectionTimeoutError` → 424 via `ErrorHandlers`.
- `/health` calls `MongoDBService.check_connection()` (a ping) → 200 or 424.

## 4. Sync vs async

| App | Client |
|---|---|
| FastAPI (async routes) | `AsyncMongoClient`, `await` every call |
| FastMCP server with async tools | `AsyncMongoClient` |
| FastMCP sync tools / existing sync code in an async server | `MongoClient`, calls wrapped in `await asyncio.to_thread(...)` |
| Flask | `MongoClient` |

A blocking `MongoClient` call inside `async def` freezes the event loop: every other request waits. Motor (`motor.motor_asyncio`) is deprecated in favour of PyMongo's own async API; migrate when touching that code.

## 5. Wiring

FastAPI:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect shared clients at startup and close them at shutdown."""
    await MongoDBService.connect()
    yield
    await MongoDBService.close()
```

Flask: `MongoDBService.connect()` (sync variant) inside `create_app()`, `atexit` or the app teardown for `close()`.

FastMCP: connect in the server's lifespan or `main.py` before `run`; never crash the server when MongoDB is down. Tools that need MongoDB return a `ToolError` / 424 per call; `tools/list` and tools that don't touch MongoDB keep working (see `mcp-spider`).

## 6. Why not connect per request

| Connect per request/query | One shared client |
|---|---|
| TCP + TLS + auth each time (10–200 ms) | Reused connection (~1 ms) |
| Bursts exceed the server's connection limit | Pool caps connections; extra operations wait briefly |
| Background monitor threads created and destroyed constantly | Created once |
| A forgotten `close()` leaks clients | Closed once at shutdown |

Only serverless functions (AWS Lambda) differ, and even there the client is created once outside the handler.
