import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    """MCP server settings loaded once from environment variables."""

    app_name: str
    mcp_host: str
    mcp_port: int
    log_level: str
    log_to_file: bool
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_issuer: str
    jwt_audience: str
    cors_origins: list[str]

    @classmethod
    def from_environment(cls) -> "AppConfig":
        """Build and validate settings from environment variables."""
        config = cls(
            app_name=os.getenv("APP_NAME", "MCP Server"),
            mcp_host=os.getenv("MCP_HOST", "127.0.0.1"),
            mcp_port=int(os.getenv("MCP_PORT", "8765")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_to_file=os.getenv("LOG_TO_FILE", "false").lower() == "true",
            # Shared with the backend that issues tokens (HS256 between services the user owns).
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            jwt_issuer=os.getenv("JWT_ISSUER", "rag-chatbot"),
            jwt_audience=os.getenv("JWT_AUDIENCE", "mcp-server"),
            cors_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()],
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Fail fast when the shared secret is missing or weak."""
        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be set and at least 32 characters long.")


settings = AppConfig.from_environment()
