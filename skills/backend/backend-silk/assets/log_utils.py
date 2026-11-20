import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings


class LogUtils:
    """Configure application logging once and provide module loggers."""

    LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    LOG_FILE = Path("logs") / "app.log"
    MAX_BYTES = 5 * 1024 * 1024
    BACKUP_COUNT = 5
    # FastAPI / FastMCP: uvicorn loggers. Flask: ("werkzeug",).
    SERVER_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")
    # Libraries that log every request at INFO; keep them quiet unless something is wrong.
    NOISY_LOGGERS = ("httpx", "httpcore", "pymongo", "urllib3", "multipart")

    @classmethod
    def configure_logging(cls) -> None:
        """Set up console and optional rotating file logging from .env settings."""
        level = cls.get_level(settings.log_level)
        formatter = logging.Formatter(cls.LOG_FORMAT)
        handlers: list[logging.Handler] = [logging.StreamHandler()]

        if settings.log_to_file:
            cls.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(RotatingFileHandler(cls.LOG_FILE, maxBytes=cls.MAX_BYTES, backupCount=cls.BACKUP_COUNT, encoding="utf-8"))

        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()

        root_logger.setLevel(level)
        for handler in handlers:
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)

        for name in cls.SERVER_LOGGERS:
            server_logger = logging.getLogger(name)
            server_logger.handlers.clear()
            server_logger.propagate = True

        for name in cls.NOISY_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)

    @staticmethod
    def get_level(level_name: str) -> int:
        """Convert LOG_LEVEL text to a logging level, failing fast on typos."""
        level = logging.getLevelName(level_name.upper())
        if not isinstance(level, int):
            raise ValueError(f"Invalid LOG_LEVEL: {level_name}")
        return level

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """Return a logger for a module; call as LogUtils.get_logger(__name__)."""
        return logging.getLogger(name)
