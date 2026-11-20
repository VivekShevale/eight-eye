from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AuthProvider
from fastmcp.server.dependencies import get_access_token
from starlette.exceptions import HTTPException
from starlette.requests import Request


class AuthUtils:
    """The calling user, always taken from the verified token, never from tool arguments."""

    @staticmethod
    def get_user_id() -> str:
        """Inside a tool: the verified token's subject."""
        access_token = get_access_token()
        user_id = access_token.claims.get("sub") if access_token else None
        if not user_id:
            raise ToolError("UNAUTHENTICATED: Authentication is required.")
        return user_id

    @staticmethod
    async def get_request_user_id(request: Request, auth: AuthProvider) -> str:
        """Inside a custom route (not covered by the MCP auth): verify the Bearer token manually."""
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Authentication required.")
        access_token = await auth.verify_token(token)
        if access_token is None or not access_token.claims.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid or expired token.")
        return access_token.claims["sub"]
