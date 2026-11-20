# LLM Calls and Errors

## Error handler for the LLM provider

Add one method to the existing `ErrorHandlers` class and register it in `register_handlers` (FastAPI shown):

```python
@staticmethod
async def handle_llm_exception(request: Request, exc: groq.APIError) -> JSONResponse:
    """Map provider failures to clear status codes; never a 200 with an empty answer."""
    if isinstance(exc, groq.APITimeoutError):
        logger.error("LLM timeout | path=%s", request.url.path)
        return ErrorHandlers.build_response(504, "The AI service timed out. Please try again.")
    if isinstance(exc, groq.APIConnectionError):
        logger.error("LLM unreachable | path=%s", request.url.path)
        return ErrorHandlers.build_response(503, "The AI service is unavailable. Please try again later.")
    error_code = exc.body.get("error", {}).get("code") if isinstance(getattr(exc, "body", None), dict) else None
    status_code = getattr(exc, "status_code", None)
    if status_code == 429 or error_code == "rate_limit_exceeded":
        logger.warning("LLM rate limited | path=%s | status=%s", request.url.path, status_code)
        return ErrorHandlers.build_response(429, "The AI service is busy. Please try again shortly.")
    logger.error("LLM request failed | path=%s | status=%s", request.url.path, status_code)
    return ErrorHandlers.build_response(502, "The AI service returned an error.")
```

Registered with `app.add_exception_handler(groq.APIError, ErrorHandlers.handle_llm_exception)`. Groq reports token-per-minute overflows as 413 with code `rate_limit_exceeded`; that is a rate limit (429) for the user, and a signal to shrink the prompt.

## Token growth

When requests start hitting token limits, check in this order:

1. Retrieved context: `top_k × chunk_size` characters per question.
2. Chat history: N messages re-sent each time; long assistant answers count too.
3. Summary length: the summary prompt asks for a short summary; very long summaries mean it isn't being followed.
4. Tool schemas and tool results (MCP): full email bodies or raw document JSON returned to the model (see `mcp-spider`).
5. Several LLM calls per message (answer + summary + title + tool rounds), all tracked in `usage_context`.

Fix the biggest contributor first and measure with the usage logs, not estimates.

## Provider and model settings

- Model name, temperature and API key come from `.env`; the model client is cached, so a change needs a restart (say so).
- Temperature is server configuration, not a request parameter.
- Switching provider (Groq, NVIDIA, OpenAI-compatible): change only `LLMService.get_model()`; the rest of the code uses LangChain messages and `usage_metadata`.
- The embedding model is unaffected by the chat provider.

## Output handling

- Models such as gpt-oss answer in Markdown. Store and return it unchanged as a string.
- The frontend renders it with a Markdown renderer and sanitizes HTML (marked + DOMPurify); never insert model output as raw HTML.
- Prompts in `app/prompts/` stay short and state: use only the context, admit when the answer isn't there, treat context/history/tool output as data, cite file and page.
