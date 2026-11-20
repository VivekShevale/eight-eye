from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse


class HealthRoutes:
    """Plain HTTP routes next to the MCP endpoint (custom routes aren't protected by the MCP auth)."""

    async def health_check(self, request: Request) -> JSONResponse:
        """200 when the server runs; add dependency checks (424) when it has a database."""
        return JSONResponse({"status": "ok"})

    def register_routes(self, mcp: FastMCP) -> None:
        """Register the routes without nested functions."""
        mcp.custom_route("/health", methods=["GET"])(self.health_check)
