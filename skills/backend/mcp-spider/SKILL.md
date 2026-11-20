---
name: mcp-spider
description: Builds and maintains MCP servers with FastMCP and MCP clients inside Python backends. Server side covers tools as thin classes registered with add_tool, services doing the work, constructor wiring in one factory, JWT verification (HS256 shared secret, issuer and audience), user from the token, ToolError with stable error codes, masked errors, custom routes, streamable HTTP. Client side covers one MCPClientService forwarding the user's token, timeout/unreachable/rejected mapping to 504/503/502, and an LLM tool loop with an allow-list, round limit and a fixed reply on tool failure so the model never invents results. Also short tool descriptions, small tool results, and MCP evaluation (only when asked). Use this whenever the user builds or changes an MCP server, MCP tools, an MCP client, LLM tool calling, Gmail/Docs/Office-style integrations exposed to an LLM, or debugs MCP errors, even if they just say "make this callable by the chatbot". Apply together with backend-silk.
---

# MCP Spider

Builds MCP servers (FastMCP) and the clients that call them from Python backends. Load these too:

- `backend-silk` (always): layers, errors, logging, config, cross-repo rules (`references/cross-repo-communication.md` there).
- `fastapi-spider` and `rag-spider` for the client side (the chatbot backend), `mongodb-silk` when the server stores data.

## Server structure

```text
mcp_server/
├── app/
│   ├── main.py            # logging, create the server, http_app(streamable-http) + CORS, uvicorn
│   ├── server.py          # MCPServerFactory: auth, services, tools, routes wired by constructor
│   ├── config.py          # frozen dataclass settings from .env
│   ├── tools/             # <domain>_tools.py: classes of @tool() methods + register_tools(mcp)
│   ├── services/          # the real work: APIs, database, credentials
│   ├── routes/            # custom HTTP routes (health, OAuth callbacks) as classes with register_routes
│   └── utils/             # log_utils, auth_utils, error/encryption utils
├── .env  .env.example  .gitignore  requirements.txt  README.md
```

Tools are the routes of an MCP server: thin, one service call, the user from the token. There is no helpers layer (helpers that would only forward to services add nothing); services hold the logic and raise `ToolError` for expected failures. Starter (tested): `assets/server/`.

## Server rules

1. **Tools**: a class per domain, `@tool()` on methods, `register_tools(mcp)` calling `mcp.add_tool(self.method)`. One short docstring sentence per tool (it's the description the model sees, paid for in tokens on every request). Type-hinted arguments; no Pydantic models for simple tools. Rules for granularity, arguments and return values: `references/tool-design.md`.
2. **Identity**: `AuthUtils.get_user_id()` reads the verified token's `sub`. Never accept a user id, email or owner as a tool argument.
3. **Auth**: `JWTVerifier(public_key=JWT_SECRET_KEY, algorithm="HS256", issuer=..., audience=...)` with the secret shared with the backend that issues tokens. RS256/PEM key pairs between two services the user owns are over-engineering. Custom routes are not covered by MCP auth: verify with `AuthUtils.get_request_user_id(request, auth)`.
4. **Errors**: expected failures raise `ToolError("CODE: message")` (`NOT_FOUND`, `INVALID_ARGUMENT`, `GOOGLE_ACCOUNT_NOT_CONNECTED`, ...); the server is created with `mask_error_details=True` so unexpected exceptions reach the client as a generic failure while the traceback is logged. Never return an error dict as a successful result.
5. **Wiring**: every object is created once in `MCPServerFactory.create_server()` and passed by constructor; constructors do no I/O (no index creation, no network calls).
6. **No nested functions**: custom routes are methods registered with `mcp.custom_route(path, methods=[...])(self.handler)`.
7. **Startup never depends on other systems**: the server starts when MongoDB or a third-party API is down; affected tools fail per call (`DATABASE_UNAVAILABLE`), `tools/list` and unaffected tools keep working, `/health` reports 424. Details: `references/server.md`.
8. **Sync code**: FastMCP runs sync tools in a worker thread by default, so sync SDKs (Google API client, PyMongo `MongoClient`) don't block; async tools must use async clients or `asyncio.to_thread`.
9. **Run**: `python -m app.main` (or `uvicorn app.main:app --port 8765`); the MCP endpoint is `/mcp`. CORS lists the frontend origin and the MCP headers (`Mcp-Session-Id`, `Mcp-Protocol-Version`).

## Client rules (inside the backend that uses the tools)

Starters (tested): `assets/client/app/services/mcp_client_service.py`, `assistant_service.py`.

1. **One client service** (`MCPClientService`) is the only code that talks to the MCP server. It forwards the end user's JWT, sets a timeout, and maps failures: timeout → 504, unreachable → 503, rejected token or protocol error → 502 (a configuration problem between the repos). FastMCP wraps network errors (`RuntimeError("Client failed to connect")` around `httpx2`/`ConnectionRefusedError`), so the service walks the exception chain instead of catching one library's class.
2. **Tool errors are data**: `call_tool(..., raise_on_error=False)` and a normalized `{"ok", "content"}` / `{"ok": False, "error_code", "message"}` result.
3. **Tool loop** (`AssistantService`): convert MCP tool definitions for `bind_tools` (binding only exposes tools; the backend executes them), allow only discovered tool names, run tool calls one by one, cap rounds at `MCP_MAX_TOOL_ROUNDS` (5) and then make one final call without tools using the collected results.
4. **A failed tool ends the turn with a fixed reply** chosen by error code (`FAILURE_MESSAGES`), with no further LLM call. Handing the error back to the model is how invented "fallback" content happened before.
5. **Don't parse tool results as JSON to detect errors**: plain-text results are valid; the `ok` flag decides.
6. **RAG + tools**: when the assistant has tools, a question with no retrieved chunks still goes to the model (it may need a tool), unlike plain RAG.
7. **Every LLM call in the loop is tracked** in `usage_context`; tool schemas and tool results are the usual cause of token-limit errors (`rag-spider/references/llm-and-errors.md`).
8. Config: `MCP_SERVER_URL`, `MCP_TIMEOUT_SECONDS` (30), `MCP_MAX_TOOL_ROUNDS` (5) in `.env`.

Prompt, wiring and the cross-repo contract: `references/client.md`.

## Evaluation

Only when evaluation is requested; the P0–P3 list, golden prompt format and rules: `references/evaluation.md`.

## Reference files

| File | Read when |
|---|---|
| `references/tool-design.md` | Adding or changing tools: names, descriptions, arguments, results, errors, safety |
| `references/server.md` | Server setup, auth, custom routes, OAuth for third-party APIs, database availability, running |
| `references/client.md` | Calling MCP from a backend: client service, tool loop, prompts, contract between repos |
| `references/evaluation.md` | The user asks to evaluate tool selection, fallbacks, isolation, latency, tokens, models |

## Assets

| File | Becomes |
|---|---|
| `assets/server/app/*` | the MCP server's `app/` (plus `log_utils.py` from `backend-silk`; example `NoteTools`/`NoteService` to rename for the real domain) |
| `assets/client/app/services/mcp_client_service.py`, `assistant_service.py` | the backend's `app/services/` |
