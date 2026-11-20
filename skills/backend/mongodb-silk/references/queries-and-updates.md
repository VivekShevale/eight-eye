# Queries and Updates

## Contents
1. Create
2. Read one, ownership and ids
3. A complete list endpoint
4. Updates and upserts
5. Deletes across collections
6. Aggregations
7. Transactions

## 1. Create

```python
users = await MongoDBService.get_collection("users")
document = {"email": email, "password_hash": password_hash, "created_at": now, "updated_at": now}
try:
    result = await users.insert_one(document)
except DuplicateKeyError as exc:
    raise HTTPException(status_code=409, detail="Email is already registered.") from exc
user_id = str(result.inserted_id)
```

- Check the cheap things first (email format, duplicate lookup) before expensive ones (password hashing); keep the unique index as the race guard.
- `now = datetime.now(timezone.utc)` computed once per operation.
- Several related documents: `insert_many([...], ordered=True)`.

## 2. Read one, ownership and ids

```python
if not ObjectId.is_valid(expense_id):
    raise HTTPException(status_code=404, detail="Expense not found.")
expenses = await MongoDBService.get_collection("expenses")
expense = await expenses.find_one({"_id": ObjectId(expense_id), "user_id": user_id})
if expense is None:
    raise HTTPException(status_code=404, detail="Expense not found.")
```

- `user_id` in the filter, not a check after loading: one query, and other users' documents are indistinguishable from missing ones.
- Convert `_id` to `id: str` in the response schema (e.g. a `from_document` classmethod on the response model).
- Projection to skip large or private fields: `find_one(filter, {"password_hash": 0})`.

## 3. A complete list endpoint

```python
@classmethod
async def list_documents(cls, user_id: str, params: DocumentListParams) -> DocumentListResponse:
    """Return one page of the user's documents."""
    query = cls.build_document_filter(user_id, params)
    documents = await MongoDBService.get_collection("documents")
    total = await documents.count_documents(query)
    cursor = (
        documents.find(query, {"user_id": 0})
        .sort([("uploaded_at", -1), ("_id", -1)])
        .skip((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )
    items = [DocumentResponse.from_document(document) async for document in cursor]
    return DocumentListResponse(items=items, page=params.page, page_size=params.page_size, total=total, total_pages=(total + params.page_size - 1) // params.page_size)

@staticmethod
def build_document_filter(user_id: str, params: DocumentListParams) -> dict:
    """Build the MongoDB filter for the document list."""
    query: dict = {"user_id": user_id}
    if params.search:
        query["filename"] = {"$regex": re.escape(params.search), "$options": "i"}
    if params.start_date or params.end_date:
        query["uploaded_at"] = {}
        if params.start_date:
            query["uploaded_at"]["$gte"] = params.start_date
        if params.end_date:
            query["uploaded_at"]["$lt"] = params.end_date + timedelta(days=1)
    return query
```

- Index for this query: `[("user_id", 1), ("uploaded_at", -1)]`.
- `re.escape` stops user input from being interpreted as a regex (and from slow patterns).
- Sort ends with `_id` so pages are stable. `skip` gets slow on very deep pages; for large collections page by range (`{"_id": {"$lt": last_id}}`).
- Several values: `{"document_id": {"$in": ids}}`. Don't wrap a single condition in `$and`.

## 4. Updates and upserts

```python
chats = await MongoDBService.get_collection("chats")
chat = await chats.find_one_and_update(
    {"_id": chat_id, "user_id": user_id},
    {"$set": {"title": payload.title, "updated_at": datetime.now(timezone.utc)}},
    return_document=ReturnDocument.AFTER,
)
if chat is None:
    raise HTTPException(status_code=404, detail="Chat not found.")
```

- Partial updates: `$set` only the fields the client sent (`payload.model_dump(exclude_unset=True)`); empty body → 400.
- Counters and lists: `$inc`, `$push` (with `$slice` to keep a bounded list), `$pull`.
- Upsert (create or update one document per key): `update_one({"user_id": u, "provider": "google"}, {"$set": {...}, "$setOnInsert": {"created_at": now}}, upsert=True)`, with a unique index on the key.
- Single-use records (OAuth state): `find_one_and_delete({"_id": state, "expires_at": {"$gt": now}})`.

## 5. Deletes across collections

Deleting a parent removes everything that belongs to it, children first, parent last, all filtered by `user_id`:

```text
delete_many messages {chat_id, user_id} -> delete_one chat {_id, user_id}
account deletion: vector chunks, files on disk, usage_logs, messages, chats, documents -> users last
```

Check `deleted_count` on the parent delete to return 404 when nothing matched. When other stores are involved (vector store, files), delete in an order that leaves no orphaned private data if a step fails, and log each step.

## 6. Aggregations

Use `aggregate` for summaries (totals per category, usage per day) instead of loading documents into Python:

```python
pipeline = [
    {"$match": {"user_id": user_id, "created_at": {"$gte": start}}},
    {"$group": {"_id": "$category", "total": {"$sum": "$amount"}}},
    {"$sort": {"total": -1}},
]
rows = [row async for row in await collection.aggregate(pipeline)]
```

Always `$match` on `user_id` first so the index is used and data stays scoped.

## 7. Transactions

- Require a replica set or Atlas; a local standalone `mongod` rejects them.
- Prefer designs where one document write is enough (embedding, upserts, `$push`).
- When several collections must change together:

```python
async with MongoDBService.client.start_session() as session:
    async with await session.start_transaction():
        await chats.insert_one(chat, session=session)
        await messages.insert_one(message, session=session)
```

Keep transactions short and never call an LLM or external API inside one.
