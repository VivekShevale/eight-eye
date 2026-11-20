import os
from dataclasses import dataclass

from dotenv import load_dotenv

# The only place .env is loaded; every module imports `settings` from here.
load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    """Application settings loaded once from environment variables."""

    app_name: str
    log_level: str
    log_to_file: bool
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    cors_origins: list[str]

    @classmethod
    def from_environment(cls) -> "AppConfig":
        """Build and validate settings from environment variables."""
        config = cls(
            app_name=os.getenv("APP_NAME", "Backend API"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_to_file=os.getenv("LOG_TO_FILE", "false").lower() == "true",
            # Not validated here: a missing or wrong database URL makes DB endpoints return 424,
            # the app itself still starts.
            database_url=os.getenv("DATABASE_URL", ""),
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
            cors_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()],
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Fail fast at startup when a required secret is missing or weak."""
        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be set and at least 32 characters long.")
        if self.access_token_expire_minutes <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be a positive number.")


settings = AppConfig.from_environment()
