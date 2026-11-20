# Testing

Tests cover critical paths.

## Stack

- Node's built-in runner: `node --test "tests/**/*.test.js"` (no Jest/Mocha needed; a bare folder path like `node --test tests/` fails on Node 22).
- `supertest` against the exported `app` (no running server, no port).
- `mongodb-memory-server` for a real, throwaway MongoDB. It downloads a MongoDB binary (a few hundred MB) on first use; set `MONGOMS_DOWNLOAD_DIR` to a drive with space. SQL projects use a separate test database URL and `prisma migrate reset --force` before the run.

## Pattern

`assets/server/tests/app.test.js`:

1. Start the memory server and set `MONGODB_URI`, `JWT_SECRET`, `LOG_LEVEL=silent` **before** importing the app (config is read at import).
2. `const { default: app } = await import("../app.js")` (dynamic import after the env is set).
3. `before`: `connectDB()`; `after`: `disconnectDB()` and `mongo.stop()`.
4. A `registerAndLogin(email)` helper returns the `Authorization` header.

## What to cover

| Area | Cases |
|---|---|
| Auth | register 201, duplicate 409, weak password 400 (not echoed), unknown field 400, wrong password and unknown email both 401 with one message, missing/malformed/non-Bearer token 401 |
| Ownership | another user's record → 404 on get, patch, delete; lists never include it; invalid id → 404 |
| Validation | negative amounts, server-owned fields (`user`) rejected, page/pageSize bounds, reversed date range, empty PATCH and `null` fields → 400 |
| Search | regex characters in the search term are treated literally |
| Response shapes | single items and list items expose exactly the response-schema keys (no `_id`, `__v`, `password`, `user`) |
| Errors | unknown route and invalid JSON use the shared shape; database disconnected → 424 without leaking the URI |
| External services | AI/storage services mocked (`mock.method(aiService, "enhanceSummary", ...)` from `node:test`): success, timeout 504, rate limit 429 |

## Running

```bat
npm test
```
