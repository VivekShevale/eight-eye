import uvicorn
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.server import MCPServerFactory
from app.utils.log_utils import LogUtils

LogUtils.configure_logging()
logger = LogUtils.get_logger(__name__)

mcp = MCPServerFactory.create_server()
app = mcp.http_app(
    transport="streamable-http",
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "Accept", "Mcp-Session-Id", "Mcp-Protocol-Version"],
        ),
    ],
)

if __name__ == "__main__":
    logger.info("Starting MCP server | host=%s | port=%s", settings.mcp_host, settings.mcp_port)
    uvicorn.run(app, host=settings.mcp_host, port=settings.mcp_port)
