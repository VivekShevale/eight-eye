# Communication Between Repositories

Applies when one of your services calls another (RAG backend → MCP server, API → worker service) or any external HTTP API.

## Contents
1. Rules
2. The client class
3. Error contract and mapping
4. Auth between services
5. Health and startup
6. Keeping both repos in sync

## 1. Rules

- Each repository owns its own data and database. Another repo never reads or writes it directly; it calls an API.
- One client class per remote service (e.g. `app/services/mcp_client.py` → `MCPClientService`, `app/services/billing_client.py`). Nothing else in the codebase talks to that service.
- The base URL comes from `.env` (`MCP_SERVER_URL`, `BILLING_API_URL`), never hardcoded, including in the frontend.
- Every call has an explicit timeout. Connect timeout short (about 5 s); read timeout sized to the operation.
- Retry only idempotent calls (GET, listing tools), at most 2–3 times with a short backoff. Never blindly retry calls that create or send something (email, document, payment).
- Each repository starts and runs on its own even when the other is down.

## 2. The client class

```python
class BillingClientService:
    """Handle communication with the billing service."""

    @classmethod
    async def get_invoice(cls, access_token: str, invoice_id: str) -> dict:
        """Fetch one invoice for the authenticated user."""
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(base_url=settings.billing_api_url, timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                response = await client.get(f"/api/v1/invoices/{invoice_id}", headers={"Authorization": f"Bearer {access_token}"})
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="Billing service timed out.") from exc
        except httpx.ConnectError as exc:
            raise HTTPException(status_code=503, detail="Billing service is unavailable. Please try again later.") from exc
        finally:
            logger.info("Billing call | operation=get_invoice | duration_ms=%.0f", (time.perf_counter() - started) * 1000)
        return cls.handle_response(response)
```

`handle_response` applies the mapping table in section 3 (424 passthrough, 401/403 → 502, business 4xx passthrough, 5xx → 502).

Libraries sometimes wrap the original network error: FastMCP raises `RuntimeError("Client failed to connect")` around `httpx2.ConnectError` and `ConnectionRefusedError`, so catching `httpx.ConnectError` never fires. For such clients, walk the exception chain (`__cause__`, `__context__`, exception-group members) once in the client class and check for built-in `ConnectionError` / `TimeoutError`; the tested implementation is `mcp-spider/assets/client/app/services/mcp_client_service.py`.

The client may raise `HTTPException` because it sits at the boundary where a remote failure becomes our API's failure. Keep the mapping in this one class.

## 3. Error contract and mapping

The called repository returns the shared `ErrorResponse` plus a stable `error_code` when the caller must react to it. The caller maps responses like this:

| What happened | Caller returns | Log level |
|---|---|---|
| Connection refused / DNS failure | 503 "X is unavailable" | ERROR |
| Timeout | 504 "X timed out" | ERROR |
| Remote returned 424 (its DB is down) | 424, keep its message | ERROR |
| Remote returned 401/403 for our forwarded token | 502 (it's our configuration bug, not the user's) | ERROR |
| Remote returned 404 / 409 / 400 for business reasons | Same status, remote's message if safe to show | WARNING |
| Remote returned 5xx or invalid JSON | 502 "X returned an error" | ERROR |
| MCP tool result with `isError` | Stable `error_code` (e.g. `GOOGLE_ACCOUNT_NOT_CONNECTED`), stop the tool loop, fixed message to the user | WARNING |

Never pass the remote's raw error text, traceback or internal URL through to our user.

## 4. Auth between services

- Forward the end user's own JWT (`Authorization: Bearer <token>`); don't invent service-level super tokens.
- Both repos share the secret (`JWT_SECRET_KEY`, HS256) via their own `.env`. The token carries `iss` (issuer service) and `aud` (list of services allowed to accept it); each receiver checks both.
- The receiver takes the user id only from the verified `sub` claim, never from a tool argument or request body.
- The token is held in memory for the request only; never stored or logged.

## 5. Health and startup

- Every service exposes `/health`: returns 200 when it and its dependencies work, 424 when its database is down.
- The caller does **not** check health before every call. Only after a call fails, it may call `/health` to tell "service down" (503) apart from "service up but its DB is down" (424).
- No startup dependency between repos: a missing MCP server makes MCP features return 503; the rest of the app keeps working.

## 6. Keeping both repos in sync

- Shared settings (secret, issuer, audience, base URLs, error codes) are listed in both `.env.example` files and both READMEs.
- When one side changes a contract (endpoint, argument, error code, auth algorithm), update the other side in the same change, with one commit per repo.
- Log outbound calls with target, operation, status and `duration_ms`. An optional `X-Request-ID` header, generated by the first service and logged by both, makes matching logs across repos easy; add it when debugging cross-repo flows gets painful, not before.
