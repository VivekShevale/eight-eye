from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier

from app.config import settings
from app.routes.health_routes import HealthRoutes
from app.services.note_service import NoteService
from app.tools.note_tools import NoteTools


class MCPServerFactory:
    """Build the server and wire services into tools by constructor (the one place objects are created)."""

    @staticmethod
    def create_auth() -> JWTVerifier:
        """Verify Bearer tokens issued by the backend: shared secret, issuer and audience."""
        return JWTVerifier(public_key=settings.jwt_secret_key, algorithm=settings.jwt_algorithm, issuer=settings.jwt_issuer, audience=settings.jwt_audience)

    @classmethod
    def create_server(cls) -> FastMCP:
        """Create the authenticated server with every tool and route registered."""
        mcp = FastMCP(name=settings.app_name, instructions="Note tools for the authenticated user.", auth=cls.create_auth(), mask_error_details=True)
        NoteTools(NoteService()).register_tools(mcp)
        HealthRoutes().register_routes(mcp)
        return mcp
