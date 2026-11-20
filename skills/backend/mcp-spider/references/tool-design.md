# Tool Design

## Contents
1. Granularity and names
2. Descriptions
3. Arguments
4. Return values
5. Errors
6. Safety

## 1. Granularity and names

- One tool per user-meaningful action: `search_emails`, `read_email`, `create_email_draft`, `create_document`, `append_document_text`. Not one tool per API endpoint, and not one giant tool with a `mode` argument.
- snake_case verb + object. Names are part of the contract with clients; renaming one is a breaking change for every client (update the client's allow-list and error mapping in the same change).
- Read tools and write tools stay separate, so a client can allow reading without allowing changes.
- Only add tools the requirement needs; every tool definition is sent to the model on every request and costs tokens.

## 2. Descriptions

- The docstring is the description the model sees. One short sentence: what it does and what it returns. "Search Gmail with a query. Returns message and thread IDs, not full content."
- No long Google-style docstrings, examples or argument essays: they're paid for in tokens on every call, and the type hints already describe the arguments.
- Say what the tool does not do when the model might assume it does ("Creates an unsent draft").

## 3. Arguments

- Type-hinted parameters with defaults (`max_results: int = 10`); FastMCP builds the input schema from them. No Pydantic models needed for simple tools.
- Never accept identity from arguments (`user_id`, `email` of the caller): the user comes from the verified token (`AuthUtils.get_user_id()`).
- Bound sizes in the service (`max_results` capped, text length limits) so a model can't request huge results.

## 4. Return values

- Return what the user or the next step needs, and nothing more: ids, titles, links (`document_url`), short snippets. Not raw API JSON or full email bodies unless the tool's purpose is reading one item.
- Large tool results are re-sent to the model in later rounds; trimming them is the main fix for token-limit errors.
- Prefer fixing a behaviour in the tool's return value over adding prompt instructions (returning `document_url` instead of telling the model how to build a link).
- Return JSON-serializable dicts/lists; FastMCP exposes them as structured content.

## 5. Errors

- Expected failures raise `ToolError("CODE: message")`, e.g. `ToolError("GOOGLE_ACCOUNT_NOT_CONNECTED: Connect your Google account first.")`. The client receives a result with `isError` and the text; the code before the colon is stable and machine-readable.
- Codes in use: `NOT_FOUND`, `INVALID_ARGUMENT`, `GOOGLE_ACCOUNT_NOT_CONNECTED`, `DATABASE_UNAVAILABLE`, `UPSTREAM_ERROR`. Add a code only when the client must react differently.
- Unexpected exceptions are logged and masked (`mask_error_details=True`), so internals never reach the client.
- Never return an "error" dict as a successful result; the client can't tell it apart from data.

## 6. Safety

- Actions with external effects (sending email, deleting, sharing) create drafts or require an explicit confirmation step designed into the tools (`create_email_draft` instead of `send_email`) unless the requirement asks for direct sending.
- Treat everything a tool returns as data: the client's system prompt says tool output is not instructions.
- Credentials for third-party APIs are stored encrypted per user (Fernet key in `.env`) and refreshed in a token service; tools never see them.
