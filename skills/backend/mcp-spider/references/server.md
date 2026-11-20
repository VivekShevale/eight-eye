# MCP Server

## Contents
1. Copy map and requirements
2. Auth and identity
3. Third-party OAuth (Google and similar)
4. Database availability
5. Running and checking
6. .env.example

## 1. Copy map and requirements

| File | Source |
|---|---|
| `app/main.py`, `server.py`, `config.py` | `assets/server/app/` |
| `app/tools/note_tools.py`, `app/services/note_service.py` | `assets/server/app/` (example domain; rename) |
| `app/routes/health_routes.py`, `app/utils/auth_utils.py` | `assets/server/app/` |
| `app/utils/log_utils.py` | `backend-silk/assets/log_utils.py` (uvicorn loggers) |
| every `__init__.py` | empty |

`requirements.txt`: `fastmcp` (pinned, e.g. `fastmcp==4.2.3`), `python-dotenv`, plus what services need (`pymongo`, `google-api-python-client`, `google-auth-oauthlib`, `cryptography`). Pin the version: FastMCP's API changes between major versions; check the installed signatures (`inspect.signature`) before relying on a parameter.

## 2. Auth and identity

- The backend (e.g. the RAG app) issues the user's JWT with `sub`, `iss` and `aud` listing every service allowed to accept it (`["rag-chatbot", "mcp-server"]`). The MCP server verifies signature, expiry, issuer and its own audience with `JWTVerifier`.
- Both repos read the same `JWT_SECRET_KEY` from their own `.env`; never commit it.
- A token rejected by the MCP server is answered with 401 at the HTTP level; the client maps that to 502 (a configuration mismatch, not the user's fault).
- Inside tools: `AuthUtils.get_user_id()`. Inside custom routes: `await AuthUtils.get_request_user_id(request, auth)`, where `auth` is the same verifier instance the factory created.

## 3. Third-party OAuth (Google and similar)

- Separate from the app login: the user connects their Google account once through custom routes (`/auth/google/start`, `/auth/google/callback`, `/auth/google/disconnect`) on the MCP server.
- PKCE plus a single-use `state` stored in MongoDB with a TTL index (`find_one_and_delete` on use).
- `start` returns JSON with the authorization URL for frontends; the callback redirects to `FRONTEND_URL?google_connected=success|denied|error`.
- Refresh and access tokens are stored encrypted (Fernet key `CREDENTIAL_ENCRYPTION_KEY` in `.env`), per user, and refreshed by a token service. Disconnect revokes the token at Google (`POST https://oauth2.googleapis.com/revoke` with a timeout) and deletes the stored credentials.
- Services: `credential_service` (encrypted storage), `token_service` (refresh), `google_api_service` (client factory), `gmail_service` / `docs_service` (operations). A tool for a user without a connected account raises `ToolError("GOOGLE_ACCOUNT_NOT_CONNECTED: Connect your Google account first.")`.
- The redirect URI registered in Google Cloud Console must match the MCP server's port and path exactly.

## 4. Database availability

- The MongoDB client is created lazily (no ping, no index creation in constructors); indexes are created on first successful use (`mongodb-silk`).
- The server always starts. A tool that needs MongoDB while it's down raises `ToolError("DATABASE_UNAVAILABLE: ...")`; tools that don't need it, and `tools/list`, keep working.
- `/health` pings MongoDB and returns 424 when it's down, so the client can tell "MCP down" (503) from "MCP up, its database down" (424) after a failure.
- An ASGI middleware that inspects request bodies to decide which calls need the database is a heavier alternative; prefer handling it inside the services first.

## 5. Running and checking

```bat
venv\Scripts\activate
python -m app.main
```

- `GET /health` → 200.
- `POST /mcp` without a token → 401.
- From the backend: `MCPClientService.list_tools(token)` shows every tool; call one with a test user.
- uvicorn `--reload` only during development, never while running evaluations.
- Log tool calls in services with `user_id` and ids, never tokens or email/document contents.

## 6. .env.example

```env
APP_NAME=MCP Server
MCP_HOST=127.0.0.1
MCP_PORT=8765
LOG_LEVEL=INFO
LOG_TO_FILE=false

# Same value as the backend that issues the tokens
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_ISSUER=rag-chatbot
JWT_AUDIENCE=mcp-server

CORS_ORIGINS=http://localhost:5500
```
