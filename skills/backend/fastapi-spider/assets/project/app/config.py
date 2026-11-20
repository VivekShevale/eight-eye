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
    db_pool_size: int
    db_max_overflow: int
    db_pool_timeout: int
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
            # Not validated: a missing or unreachable database makes DB endpoints return 424; the app still starts.
            database_url=os.getenv("DATABASE_URL", ""),
            db_pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            db_max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            db_pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
            cors_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()],
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Fail fast at startup when a required secret is missing or a number is invalid."""
        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be set and at least 32 characters long.")
        if self.access_token_expire_minutes <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be a positive number.")
        if self.db_pool_size <= 0 or self.db_max_overflow < 0:
            raise ValueError("DB_POOL_SIZE must be positive and DB_MAX_OVERFLOW not negative.")


settings = AppConfig.from_environment()
