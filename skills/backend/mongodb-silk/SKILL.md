---
name: mongodb-silk
description: MongoDB standards for Python backends (FastAPI, Flask, FastMCP) using PyMongo's AsyncMongoClient or MongoClient. Covers the single shared client and connection pool, MongoDBService (connect, indexes, collections, close), startup without crashing when MongoDB is down and 424 per request, named compound, unique and TTL indexes, user-scoped queries, projections, ids, embedding vs separate collections, pagination, search, upserts and atomic updates, transactions, and DuplicateKeyError to 409. Use this whenever a project stores data in MongoDB or Atlas, designs collections or documents, writes find/update/aggregate queries, or hits errors like ServerSelectionTimeoutError, even if the user only says "store it in Mongo". Apply together with backend-silk and the framework spider.
---

# MongoDB Silk: MongoDB standards

Shared MongoDB rules for every framework spider. `backend-silk` decides the layers; this skill decides how MongoDB is used.

## The core idea

**One client per process, created at startup and shared.** A PyMongo client owns a connection pool. Each operation (`find_one`, `insert_one`, ...) borrows a connection for the few milliseconds it runs and returns it, so, unlike a SQL session, nothing is held between queries or across slow LLM calls. Creating a client per request or per query is slow (TCP + TLS + auth every time) and exhausts the server's connection limit under load.

## Layers

| Who | Does |
|---|---|
| `MongoDBService` (`app/services/mongodb_service.py`) | Creates the client and pool, pings once at startup, creates indexes, hands out collections, closes the client |
| Helper | Builds the feature query (filter with `user_id`, projection, sort, skip/limit) and calls PyMongo collection methods directly |
| `ErrorHandlers` | `ConnectionFailure` (includes `ServerSelectionTimeoutError`) and "database not configured" → 424 |

Why helpers call collection methods directly: PyMongo's methods already are the generic create/read/update/delete, and each one manages its own connection. A wrapper with `insert_one(collection, doc)` would only forward calls, which `backend-silk` forbids. The connection-handling work the SQL `DBService` does (sessions, commit, rollback) has no MongoDB equivalent outside transactions.

Template: `assets/mongodb_service.py` (async). Sync variant notes are in the file.

```python
class ChatHelper:
    """Business logic for chats."""

    @staticmethod
    async def get_chat(user_id: str, chat_id: str) -> ChatResponse:
        """Return one chat owned by the user."""
        chats = await MongoDBService.get_collection("chats")
        chat = await chats.find_one({"_id": chat_id, "user_id": user_id}, {"summary": 0})
        if chat is None:
            raise HTTPException(status_code=404, detail="Chat not found.")
        return ChatResponse.from_document(chat)
```

## Client and startup

- `AsyncMongoClient` from `pymongo` in async apps (FastAPI, FastMCP async tools). Motor is deprecated; don't add it. Sync `MongoClient` only in sync apps (Flask), or wrapped in `asyncio.to_thread` when an async server must call sync code.
- Client options from `.env` via `config.py`: `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_MAX_POOL_SIZE` (50), `MONGODB_MIN_POOL_SIZE` (0), plus fixed `serverSelectionTimeoutMS=5000`, `connectTimeoutMS=5000`, `socketTimeoutMS=20000`, `waitQueueTimeoutMS=5000`, `maxIdleTimeMS=60000`, `retryWrites=True`, `tz_aware=True` (datetimes come back timezone-aware).
- `connect()` runs once in the lifespan: create client, ping, create indexes. If MongoDB is down or `MONGODB_URI` is missing, **log and continue**: the app starts, DB endpoints return 424, and indexes are created on the first successful request.
- No ping on every request. `/health` pings.
- `close()` in the lifespan shutdown.
- Each worker has its own pool: `workers × maxPoolSize` must stay below the cluster's connection limit (Atlas tiers have caps).

Details: `references/client-and-connections.md`.

## Documents

- **ids**: every document's `_id` is its app id. Default ObjectId; when the id must exist before the insert (e.g. a file saved as `{id}.pdf`), use `str(uuid4())` as `_id`. Don't keep a second id field next to `_id`. Responses expose it as `id: str`; an invalid ObjectId in a path returns 404, not 500.
- **Ownership**: every user-owned document has `user_id`, and every filter on it includes `user_id` from the token. Another user's document returns 404.
- **Timestamps**: `created_at`, `updated_at` as `datetime.now(timezone.utc)`; `$set` `updated_at` on every update.
- **Projections**: return only needed fields; never send `password_hash`, tokens or internal fields to a response.
- **Embed or separate?** Embed data that is bounded and read with its parent (the `llm_calls` of one usage log). Use a separate collection for data that grows without limit or is paged on its own (chat messages separate from chats).
- **Don't store what can be derived** (`total_tokens` when input and output tokens are stored).
- API schemas (Pydantic) define request and response shapes. Add document model classes only if the project needs stored-shape validation; plain dicts at the DB layer are fine.

## Indexes

- Created in `MongoDBService.create_indexes()`, called from `connect()`. Never in constructors and never per request.
- Always named: `create_index([("user_id", 1), ("created_at", -1)], name="user_created_idx")`.
- Compound index matching the main list query: equality fields first (`user_id`), then the sort field.
- `unique=True` for natural keys (`email`), which also guards against two simultaneous registrations.
- TTL index for documents that expire (OAuth states, revoked tokens): `create_index("expires_at", expireAfterSeconds=0, name="expires_at_ttl")`.
- Drop indexes that a new compound index makes redundant.

## Queries and updates

- Filter, sort, count and paginate in MongoDB, never in Python.
- Pagination: `count_documents(filter)` with the same filter, then `find(filter).sort([("created_at", -1), ("_id", -1)]).skip(...).limit(...)`. For very large collections, range pagination on `_id`.
- Search: `{"title": {"$regex": re.escape(term), "$options": "i"}}` for small collections; a text index for larger ones.
- Updates use operators (`$set`, `$inc`, `$push`, `$setOnInsert`) so they're atomic on one document; never read-modify-write a whole document.
- `find_one_and_update(..., return_document=ReturnDocument.AFTER)` when the response needs the updated document; `find_one_and_delete` for single-use records.
- Multi-document transactions need a replica set (Atlas has one; a local standalone server doesn't). Prefer a document design where one write is enough.

Patterns: `references/queries-and-updates.md`.

## Errors

| Exception | Where | Response |
|---|---|---|
| `DuplicateKeyError` | Helper, around the insert/update | 409 "Email is already registered." |
| `ConnectionFailure`, `ServerSelectionTimeoutError`, `ConnectionError("Database is not configured.")` | `ErrorHandlers.handle_database_exception` | 424 "Database dependency is unavailable." |
| `OperationFailure` (bad query, auth misconfiguration) | Global handler | 500, logged |
| Invalid ObjectId string | Helper (`ObjectId.is_valid`) | 404 |

Log the error type, never the connection URI (it contains the password).

## Reference files

| File | Read when |
|---|---|
| `references/client-and-connections.md` | Setting up the client, pool tuning, startup/health, sync vs async, FastMCP servers |
| `references/queries-and-updates.md` | Writing queries, list endpoints, upserts, deletes across collections, transactions |

## Assets

| File | Becomes |
|---|---|
| `assets/mongodb_service.py` | `app/services/mongodb_service.py` |
