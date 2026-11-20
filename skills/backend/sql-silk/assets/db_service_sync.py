from typing import Any

from sqlalchemy import Engine, Select, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.utils.log_utils import LogUtils

logger = LogUtils.get_logger(__name__)


class DBService:
    """Own the SQL engine and run every database operation in its own short session.

    Flask with Flask-SQLAlchemy: drop `connect` and `close`, and make `new_session` return
    `Session(db.engine, expire_on_commit=False, autoflush=False)` (db from app.extensions).
    Flask-SQLAlchemy then owns the engine and its pool options (SQLALCHEMY_ENGINE_OPTIONS).
    """

    engine: Engine | None = None
    session_factory: sessionmaker[Session] | None = None

    @classmethod
    def connect(cls) -> None:
        """Create the engine and connection pool once at startup (no connection is opened yet)."""
        if not settings.database_url:
            logger.error("Database is not configured | setting=DATABASE_URL")
            return
        cls.engine = create_engine(settings.database_url, **cls.get_pool_options())
        cls.session_factory = sessionmaker(cls.engine, expire_on_commit=False, autoflush=False)
        logger.info("Database engine created | pool_size=%s | max_overflow=%s", settings.db_pool_size, settings.db_max_overflow)

    @staticmethod
    def get_pool_options() -> dict:
        """Pool settings for server databases; SQLite is a local file and manages its own pool."""
        if settings.database_url.startswith("sqlite"):
            return {}
        return {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout,
            "pool_recycle": 1800,
            "pool_pre_ping": True,
        }

    @classmethod
    def close(cls) -> None:
        """Close every pooled connection at shutdown."""
        if cls.engine is not None:
            cls.engine.dispose()
            logger.info("Database engine disposed")

    @classmethod
    def new_session(cls) -> Session:
        """Return a new session; ErrorHandlers maps the ConnectionError to 424."""
        if cls.session_factory is None:
            raise ConnectionError("Database is not configured.")
        return cls.session_factory()

    @classmethod
    def create(cls, records: Any | list[Any]) -> Any | list[Any]:
        """Insert one record, or a list of records in one transaction, and return them refreshed."""
        items = records if isinstance(records, list) else [records]
        with cls.new_session() as session:
            try:
                session.add_all(items)
                session.commit()
            except Exception:
                session.rollback()
                raise
            for item in items:
                session.refresh(item)
        return records

    @classmethod
    def read(cls, statement: Select, one: bool = False) -> Any:
        """Run a select statement; one=True returns a single object, a scalar or None."""
        with cls.new_session() as session:
            result = session.execute(statement)
            if one:
                return result.scalar_one_or_none()
            return list(result.scalars().all())

    @classmethod
    def update(cls, record: Any, changes: dict[str, Any] | None = None) -> Any:
        """Apply changes to a record loaded earlier, commit, and return the fresh record."""
        with cls.new_session() as session:
            try:
                merged = session.merge(record)
                for field, value in (changes or {}).items():
                    setattr(merged, field, value)
                session.commit()
            except Exception:
                session.rollback()
                raise
            session.refresh(merged)
            return merged

    @classmethod
    def delete(cls, record: Any) -> None:
        """Delete a record loaded earlier and commit."""
        with cls.new_session() as session:
            try:
                session.delete(session.merge(record))
                session.commit()
            except Exception:
                session.rollback()
                raise

    @classmethod
    def check_connection(cls) -> None:
        """Run SELECT 1 for /health; raises when the database is unreachable."""
        with cls.new_session() as session:
            session.execute(text("SELECT 1"))
