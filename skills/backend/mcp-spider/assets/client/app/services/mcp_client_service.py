import json
from collections.abc import Iterator
from time import perf_counter
from typing import NoReturn

from fastapi import HTTPException
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.types import CallToolResult, Tool

from app.config import settings
from app.utils.log_utils import LogUtils

logger = LogUtils.get_logger(__name__)


class MCPClientService:
    """The only code that talks to the MCP server. Forwards the user's token and maps MCP failures
    to our API's status codes (this is the boundary where a remote failure becomes our response).
    """

    @staticmethod
    def create_client(access_token: str) -> Client:
        """A client for one operation, authenticated with the end user's own JWT."""
        transport = StreamableHttpTransport(settings.mcp_server_url, headers={"Authorization": f"Bearer {access_token}"})
        return Client(transport, timeout=settings.mcp_timeout_seconds)

    @classmethod
    def iter_causes(cls, exc: BaseException) -> Iterator[BaseException]:
        """The exception, its causes and the members of exception groups (FastMCP wraps network errors)."""
        pending, seen = [exc], set()
        while pending:
            current = pending.pop()
            if current is None or id(current) in seen:
                continue
            seen.add(id(current))
            yield current
            pending.extend([current.__cause__, current.__context__, *getattr(current, "exceptions", ())])

    @classmethod
    def raise_http_error(cls, exc: BaseException, operation: str) -> NoReturn:
        """Timeout -> 504, server unreachable -> 503, anything else (e.g. rejected token) -> 502."""
        causes = list(cls.iter_causes(exc))
        if any(isinstance(cause, TimeoutError) or "Timeout" in type(cause).__name__ for cause in causes):
            logger.error("MCP timeout | operation=%s", operation)
            raise HTTPException(status_code=504, detail="The tool server timed out. Please try again.") from exc
        if any(isinstance(cause, ConnectionError) for cause in causes):
            logger.error("MCP unreachable | operation=%s", operation)
            raise HTTPException(status_code=503, detail="The tool server is unavailable. Please try again later.") from exc
        logger.error("MCP request failed | operation=%s | error_type=%s", operation, type(exc).__name__)
        raise HTTPException(status_code=502, detail="The tool server rejected the request.") from exc

    @staticmethod
    def normalize_result(result: CallToolResult) -> dict:
        """{"ok": True, "content": str} or {"ok": False, "error_code": str, "message": str}."""
        text = "\n".join(item.text for item in result.content if hasattr(item, "text"))
        if result.is_error:
            code, separator, message = text.partition(": ")
            if not separator or not code.replace("_", "").isalpha() or not code.isupper():
                code, message = "TOOL_FAILED", text
            return {"ok": False, "error_code": code, "message": message}
        content = json.dumps(result.structured_content, default=str) if result.structured_content is not None else text
        return {"ok": True, "content": content}

    @classmethod
    async def list_tools(cls, access_token: str) -> list[Tool]:
        """Tools the user may call."""
        try:
            async with cls.create_client(access_token) as client:
                return await client.list_tools()
        except Exception as exc:
            cls.raise_http_error(exc, "list_tools")

    @classmethod
    async def call_tool(cls, access_token: str, tool_name: str, arguments: dict | None = None) -> dict:
        """Call one tool; tool errors come back as data, transport failures as HTTP errors."""
        started_at = perf_counter()
        try:
            async with cls.create_client(access_token) as client:
                result = await client.call_tool(tool_name, arguments or {}, raise_on_error=False)
        except Exception as exc:
            cls.raise_http_error(exc, f"call_tool:{tool_name}")
        normalized = cls.normalize_result(result)
        logger.info("MCP call | tool=%s | ok=%s | duration_ms=%.0f", tool_name, normalized["ok"], (perf_counter() - started_at) * 1000)
        return normalized
