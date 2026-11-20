# Routes and Schemas

## Contents
1. Router file template
2. Dependencies: parameter, decorator, router
3. Path and query parameters
4. Body, update and response models
5. File uploads
6. Status codes and empty responses
7. Common FastAPI mistakes

## 1. Router file template

```python
expense_router = APIRouter(prefix="/api/v1/expenses", tags=["Expenses"])


@expense_router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseCreateRequest, current_user: dict = Depends(AuthUtils.get_current_user)):
    return await ExpenseHelper.create_expense(payload, current_user["user_id"])
```

- Route functions have no docstring requirement and no logic; the helper method name usually matches the route name.
- Register the router in `main.py` with `app.include_router(expense_router)`.
- Child resources: `chat_router = APIRouter(prefix="/api/v1/chats")` with `@chat_router.post("/{chat_id}/messages")`.

## 2. Dependencies: parameter, decorator, router

| Form | Use |
|---|---|
| `current_user: dict = Depends(AuthUtils.get_current_user)` | The route needs the result (user id, token). The normal case |
| `@router.post(..., dependencies=[Depends(AuthUtils.require_admin)])` | Only a check; the result is discarded |
| `APIRouter(..., dependencies=[Depends(AuthUtils.get_current_user)])` | Make every route of a router protected; keep the parameter on routes that need the value |

- A dependency that uses `return` finishes before the route runs and holds no DB connection. One that uses `yield` stays open until the response is sent; don't use `yield` dependencies for DB sessions.
- `get_current_user` returns a plain dict (`{"user_id": ..., "email": ...}`; RAG/MCP projects add `"access_token"` when the token must be forwarded to another service).
- Role checks: a small `AuthUtils.require_role(...)`-style dependency raising 403, added only when the project has roles.

## 3. Path and query parameters

- Typed path parameters (`expense_id: int`) give 422 for bad input automatically. Add `Path(ge=1)` for numeric ids if needed. MongoDB string ids are validated in the helper (invalid → 404).
- Lists take one query model:

```python
@expense_router.get("", response_model=ExpenseListResponse)
async def list_expenses(params: Annotated[ExpenseListParams, Query()], current_user: dict = Depends(AuthUtils.get_current_user)):
    return await ExpenseHelper.list_expenses(current_user["user_id"], params)
```

The model holds defaults, bounds (`page ≥ 1`, `1 ≤ page_size ≤ 100`), `extra="forbid"` and cross-field checks; violations become 422 with field details.

## 4. Body, update and response models

- Create: required fields only, constraints in `Field`, `extra="forbid"` so `user_id`, `role` or `created_by` sent by a client are rejected.
- Update (PATCH): every field optional with `= None`; the helper uses `model_dump(exclude_unset=True)`, rejects an empty body and explicit `null` (400).
- Response: only what the client needs; `from_attributes=True` to validate ORM objects; never password hashes or tokens.
- Validation that needs the database (duplicate email, ownership) is the helper's job; validation that needs only the input belongs in the schema (password policy via `field_validator` with `password-validator`).
- Money as `Decimal` with `max_digits`/`decimal_places`; it serializes as a string.

## 5. File uploads

```python
@document_router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...), current_user: dict = Depends(AuthUtils.get_current_user)):
    return await DocumentHelper.upload_document(file, current_user["user_id"])
```

The helper reads at most `max_size + 1` bytes (413 if larger), checks extension and magic bytes, stores under a UUID name, and deletes the file if later processing fails. Requires `python-multipart` (included in `fastapi[standard]`).

## 6. Status codes and empty responses

- 201 on create, 200 on read/update, 204 on delete. A 204 route returns nothing (`await Helper.delete(...)` without `return`).
- Errors come only from `HTTPException` in helpers or the central handlers, so every error has the shared shape. A helper never returns `JSONResponse({"message": ...})` for an error.

## 7. Common FastAPI mistakes

| Mistake | Fix |
|---|---|
| `Optional[str]` field without `= None` | Still required; add `= None` |
| Collection route `"/"` while the client calls `/api/v1/expenses` | Use `""`; avoid 307 redirects |
| Sync DB/SDK call inside `async def` | `await asyncio.to_thread(...)` or the async client |
| `Depends(get_db)` session held through an LLM call | DBService short sessions |
| Two `FastAPI()` objects in `main.py` | One app |
| Routers named `auth_bp` | `auth_router` |
| Parsing `request.query_params` by hand | Query model |
| Exception handlers defined inside a function | Static methods on `ErrorHandlers` |
| `uvicorn --reload` restarting on every log or eval file write | `--reload-dir app` |
