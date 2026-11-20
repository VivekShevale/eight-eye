# Errors and Edge Cases

## Contents
1. Who handles what
2. The error response
3. Status code map
4. ErrorHandlers pattern
5. Edge-case checklist
6. What the user is shown
7. Logging errors

## 1. Who handles what

| Layer | Does |
|---|---|
| Schema | Rejects malformed input automatically (FastAPI → 422; Flask parse helper → 400; DRF serializer → 400) |
| Service | Raises plain or library exceptions (`ValueError("PDF has no text layer.")`, `PyMongoError`, `OperationalError`, `httpx.ConnectError`). Never builds HTTP responses |
| Helper | Turns expected situations into HTTP errors: `raise HTTPException(404, "Expense not found.")`, `ValueError` from a service → 400, `IntegrityError` on a unique field → 409. Uses `raise ... from exc` to keep the cause |
| `ErrorHandlers` | Maps dependency exceptions centrally (DB down → 424, upstream errors → 502/503/504/429) and catches everything else as 500 |
| Route | Nothing. No try/except in routes |

Catch an exception only where you can do something meaningful with it. Never `except Exception: pass`. A broad `except Exception` is allowed only to clean up (delete an uploaded file, roll back) and must re-raise.

## 2. The error response

Every error from every project uses one schema (`assets/common_schema.py`):

```json
{"status": "error", "message": "Request validation failed.", "details": [{"field": "body.email", "message": "value is not a valid email address"}]}
```

Without field details it is simply `{"status": "error", "message": "Expense not found."}`.

- `message`: one short sentence a user can understand.
- `details`: only for field-level problems; left out of the response otherwise (handlers dump with `exclude_none=True`).
- Include `error_code` (e.g. `DATABASE_UNAVAILABLE`, `GOOGLE_ACCOUNT_NOT_CONNECTED`) only when a client or another repo must branch on the error. Add it as an optional field of `ErrorResponse`, not a second shape.
- Every handler, including dependency handlers, returns this shape. A handler that returns `{"detail": ...}` is a bug.

## 3. Status code map

| Code | When | Example message |
|---|---|---|
| 200 | Read or update succeeded | |
| 201 | Created | |
| 204 | Deleted, no body | |
| 400 | Input passed the schema but is invalid (bad PDF, start date after end date, empty update body) | "Provide at least one field to update." |
| 401 | Missing/invalid/expired token, wrong credentials | "Invalid email or password." |
| 403 | Authenticated but role not allowed (e.g. customer calling an admin action) | "You do not have permission to perform this action." |
| 404 | Missing record **or a record owned by another user** (never reveal it exists) | "Expense not found." |
| 409 | Duplicate (email, unique name) | "Email is already registered." |
| 413 | Upload or payload too large (message built from config) | "File exceeds the 10 MB limit." |
| 422 | Schema validation failed | "Request validation failed." |
| 424 | Our own required dependency is down: database, vector store, or the database behind another repo | "Database dependency is unavailable." |
| 429 | Upstream rate limit (e.g. Groq `rate_limit_exceeded`) | "The AI service is busy. Please try again shortly." |
| 502 | Upstream answered with an error or invalid data | "The AI service returned an error." |
| 503 | Another service can't be reached at all | "MCP server is unavailable. Please try again later." |
| 504 | Upstream didn't answer in time | "The AI service timed out." |
| 500 | Anything unexpected | "An unexpected error occurred." |

Never return 200 for a failed operation, including LLM calls whose error was swallowed.

Use 424 only for confirmed dependency failures (connection refused, server selection timeout, `OperationalError`). Bad credentials in config and logic bugs are 500.

## 4. ErrorHandlers pattern

One class in `app/utils/error_handlers.py`, one static method per exception type, one `register_handlers(app)` method called once from `main.py` / `create_app()`. No nested functions, no handlers defined inside the app factory. Framework code is in each framework skill; the set of handlers is:

| Handler | Maps |
|---|---|
| `handle_http_exception` | HTTP errors raised by helpers → same status, `ErrorResponse(message=detail)` |
| `handle_validation_exception` | Schema errors → 422 (400 in Flask) with `details` per field. Never echo the submitted values |
| `handle_database_exception` | `OperationalError` (SQL) / `ConnectionFailure` (MongoDB, includes `ServerSelectionTimeoutError`), and `ConnectionError("Database is not configured.")` raised by DBService → 424 |
| `handle_upstream_exception` | LLM / external API errors → 429 / 502 / 504 |
| `handle_unexpected_exception` | `Exception` → 500, `logger.exception(...)` |

Add a new handler method to this existing class when a new dependency appears; don't create a new file or class for it.

## 5. Edge-case checklist

Go through this for every endpoint before calling it done. Not every item applies; the point is to consider each.

**Input**
- Empty string and whitespace-only strings (strip, then check)
- Missing required field, extra unknown field (`extra="forbid"`), wrong type
- Explicit `null` for a non-nullable field in a PATCH
- Empty PATCH body → 400
- Very long strings, Unicode, emoji (set `max_length`)
- Numbers: zero, negative, too large (`gt=0`, `le=...`), money as `Decimal`

**Lists, filters, pagination**
- `page` ≤ 0, `page_size` 0 or above the maximum
- Start date after end date; invalid date format; time-zone of date filters (UTC)
- Filter value that matches nothing → 200 with an empty list, not 404
- Search term with special characters (use DB operators, never string-built queries)

**Records and ownership**
- Id that doesn't exist; malformed id (invalid ObjectId / UUID) → 404, not 500
- Id that belongs to another user → 404
- Duplicate create, including two requests at the same time (unique index/constraint plus catching the integrity error → 409)
- Update or delete of something already deleted
- Deleting a record others reference (cascade, protect, or block with a clear error)
- Invalid state transitions (closed ticket can't be reopened)

**Files**
- Empty file, file over the size limit (read at most limit + 1 bytes → 413)
- Wrong extension or wrong magic bytes (`%PDF-`), corrupt, encrypted, scanned (no text layer)
- Store under a generated UUID name, never the client's filename; delete the stored file if processing fails

**Dependencies**
- Database down at startup (app still starts) and mid-request (424)
- LLM rate limit, timeout, malformed response; vector store unavailable
- Another repo unreachable, slow, or returning an error (see `cross-repo-communication.md`)
- Partial failure across stores (DB record saved, vector insert failed): roll back or clean up what was written, in reverse order

**Auth**
- No token, malformed token, expired token, token for a deleted user → 401
- Role allowed? (403 only for role checks, 404 for other users' records)

## 6. What the user is shown

- A short, specific, safe sentence. Say what to do when possible ("Connect your Google account first.").
- Never: tracebacks, exception class names, SQL, hosts, ports, connection strings, file system paths, API keys, tokens.
- Login and password-reset messages never reveal whether an account exists.
- When an LLM tool or upstream call fails, return a fixed, deterministic message. Do not make a second LLM call to "explain" the failure, and never let the LLM produce substitute content as if the action succeeded.

## 7. Logging errors

- Log each failure once, at the layer that handles it. If the helper raises an `HTTPException`, the global handler logs it; the helper doesn't log it again.
- 4xx: `WARNING`, no traceback, with path and status.
- 424/5xx and dependency failures: `ERROR` via `logger.exception(...)` so the traceback goes to the log file, never to the response.
- Log the error type for dependency failures (`error_type=%s`), never the raw exception message if it can contain a connection string.
