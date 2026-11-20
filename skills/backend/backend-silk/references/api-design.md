# API Design

## Designing an endpoint

1. Understand the full requirement and list every route it needs before coding.
2. Pick the method: GET read, POST create, PATCH partial update, PUT full replace (rare), DELETE remove.
3. Define the request schema(s), the response schema, path and query parameters (see "Request and response schemas").
4. Decide auth (public, logged-in, role) and ownership rules.
5. Decide the helper method and the services it uses. The route stays a one-line call.

## Conventions

- Prefix: `/api/v1/<plural-resource>` (e.g. `/api/v1/expenses`, `/api/v1/chats/{chat_id}/messages`). Nested paths for child resources owned by a parent.
- Response model declared on every route; explicit status codes (201 create, 204 delete without body).
- Pick one trailing-slash style per project and keep it consistent; a mismatch causes 307/308 redirects.
- `/health` reports the app and its dependencies (200 or 424).
- Partial update: all-optional update schema, apply only fields the client sent (`model_dump(exclude_unset=True)`), reject explicit `null` for required columns, reject an empty body with 400.
- Never accept server-owned fields from the client: ids, `user_id`, `created_by`, `updated_by`, timestamps, status fields the server controls.

## Lists: pagination, filters, search, sort

Everything goes through URL query parameters, applied in the database. Never fetch all rows and filter in Python, and never filter on the frontend.

| Parameter | Rule |
|---|---|
| `page` | default 1, must be ≥ 1 |
| `page_size` | default 10, between 1 and 100 |
| `search` | case-insensitive match on the relevant text fields (`ilike`, `icontains`, Mongo `$regex` with escaped input or a text index) |
| filters | one parameter per field: `category`, `status`, `priority` |
| date ranges | `start_date` / `end_date` (YYYY-MM-DD, UTC); `created_at_from` / `created_at_to`; end of day as `< next day 00:00` |

Validate that range starts aren't after ends (400).

Sort deterministically: the main sort field plus a unique tiebreaker (`created_at desc, id desc`) so pages don't repeat or skip items.

Response shape for lists:

```json
{"items": [...], "page": 1, "page_size": 10, "total": 57, "total_pages": 6}
```

Use the resource name instead of `items` if the project already does (`expenses`, `documents`); keep one shape per project. Count the total from the same filtered query before applying offset/limit. DB-specific code is in `sql-silk` and `mongodb-silk`; Django uses DRF pagination.

## Request and response schemas

Every endpoint has a declared contract. No handler reads raw input or returns an object literal built on the spot.

**Requests**
- Body and query parameters each go through a request schema (`XCreateRequest`, `XUpdateRequest`, `XListParams`, action payloads such as `LoginRequest`). Path ids are typed by the router or checked in the helper.
- Request schemas reject unknown fields and never contain server-owned fields (ids, owner, `created_by`, timestamps, server-controlled status).
- Code after validation uses only the validated object, never the raw request body.

**Responses**
- Every successful body is built from a response schema: one per resource (`XResponse`), one for lists (`XListResponse`), one per action result that isn't a resource (`TokenResponse`, `UploadResult`, `HealthResponse`).
- The body is the resource itself, with no envelope; the HTTP status code says whether the request succeeded:

| Case | Status | Body |
|---|---|---|
| Read one | 200 | `XResponse` |
| List | 200 | `{"items": [...], "page", "page_size", "total", "total_pages"}` (camelCase in Node) |
| Create | 201 | `XResponse` of the created record |
| Update (PATCH) | 200 | `XResponse` of the updated record |
| Delete | 204 | empty |
| Action (login, upload, send) | 200 or 201 | its own result schema, e.g. `{"access_token", "token_type", "expires_in"}` |
| Any error | 4xx/5xx | `ErrorResponse`: `{"status": "error", "message", "details"?}` |

- The same response shape for the same resource everywhere it appears (list items and single reads use the same `XResponse`).
- Never `{"success": false, ...}` with status 200, never `{"message": "Saved successfully"}` when nothing was saved, never a different shape per route.
- Field naming is consistent within a project: snake_case in Python APIs (`page_size`, `total_pages`, `access_token`), camelCase in Node APIs (`pageSize`, `totalPages`, `accessToken`), the same style in query parameters and bodies.

**Where schemas live per framework**

| Framework | Request schemas | Response schemas |
|---|---|---|
| FastAPI | Pydantic models in `schemas/<domain>_schema.py`; query models via `Annotated[XListParams, Query()]` | Pydantic models, declared with `response_model=` on every route |
| Flask | Pydantic models in `schemas/`, validated by `RequestUtils.parse_body` / `parse_query` | Pydantic models; helpers return `XResponse.model_validate(obj).model_dump(mode="json"), status` |
| Django REST | Input serializers (create, update, action, list params) | Output serializers with `read_only_fields = fields` |
| Express (Node) | Joi schemas in `schemas/<domain>Schema.js`, run by `validate()` | Response functions in the same file (`toXResponse`, `toXListResponse`); controllers send only their result |
| FastMCP tools | Typed tool arguments | Fixed result shape per tool (same keys every call); errors via `ToolError` |

## Response content

- Response schemas expose only what the client needs. Never passwords, hashes, tokens, internal ids such as Mongo `_id` (map to a string id field), or other users' data.
- Datetimes in ISO 8601 UTC. Money as decimal strings or `Decimal`, never float.
- LLM output that is Markdown stays a Markdown string; the frontend renders it with sanitization.
