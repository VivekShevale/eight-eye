from pathlib import Path


class LoggingConfig:
    """Build Django's LOGGING dict from LOG_LEVEL and LOG_TO_FILE (the Django form of LogUtils)."""

    LOG_FORMAT = "{asctime} | {levelname} | {name} | {message}"
    MAX_BYTES = 5 * 1024 * 1024
    BACKUP_COUNT = 5

    @classmethod
    def build(cls, base_dir: Path, log_level: str, log_to_file: bool) -> dict:
        """Console always; a rotating logs/app.log only when LOG_TO_FILE=true."""
        level = log_level.upper()
        handlers = {"console": {"class": "logging.StreamHandler", "formatter": "standard"}}
        if log_to_file:
            log_directory = base_dir / "logs"
            log_directory.mkdir(parents=True, exist_ok=True)
            handlers["file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_directory / "app.log"),
                "maxBytes": cls.MAX_BYTES,
                "backupCount": cls.BACKUP_COUNT,
                "encoding": "utf-8",
                "formatter": "standard",
            }
        handler_names = list(handlers)
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"standard": {"format": cls.LOG_FORMAT, "style": "{"}},
            "handlers": handlers,
            "root": {"handlers": handler_names, "level": level},
            "loggers": {
                "django": {"handlers": handler_names, "level": level, "propagate": False},
                "django.db.backends": {"handlers": handler_names, "level": "WARNING", "propagate": False},
            },
        }
