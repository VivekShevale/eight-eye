from typing import Any

from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.utils.log_utils import LogUtils

logger = LogUtils.get_logger(__name__)


class DBService:
    """Own the SQL engine and run every database operation in its own short session."""

    engine: AsyncEngine | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None

    @classmethod
    def connect(cls) -> None:
        """Create the engine and connection pool once at startup (no connection is opened yet)."""
        if not settings.database_url:
            logger.error("Database is not configured | setting=DATABASE_URL")
            return
        cls.engine = create_async_engine(settings.database_url, **cls.get_pool_options())
        cls.session_factory = async_sessionmaker(cls.engine, expire_on_commit=False, autoflush=False)
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
    async def close(cls) -> None:
        """Close every pooled connection at shutdown."""
        if cls.engine is not None:
            await cls.engine.dispose()
            logger.info("Database engine disposed")

    @classmethod
    def new_session(cls) -> AsyncSession:
        """Return a new session; ErrorHandlers maps the ConnectionError to 424."""
        if cls.session_factory is None:
            raise ConnectionError("Database is not configured.")
        return cls.session_factory()

    @classmethod
    async def create(cls, records: Any | list[Any]) -> Any | list[Any]:
        """Insert one record, or a list of records in one transaction, and return them refreshed."""
        items = records if isinstance(records, list) else [records]
        async with cls.new_session() as session:
            try:
                session.add_all(items)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            for item in items:
                await session.refresh(item)
        return records

    @classmethod
    async def read(cls, statement: Select, one: bool = False) -> Any:
        """Run a select statement; one=True returns a single object, a scalar or None."""
        async with cls.new_session() as session:
            result = await session.execute(statement)
            if one:
                return result.scalar_one_or_none()
            return list(result.scalars().all())

    @classmethod
    async def update(cls, record: Any, changes: dict[str, Any] | None = None) -> Any:
        """Apply changes to a record loaded earlier, commit, and return the fresh record."""
        async with cls.new_session() as session:
            try:
                merged = await session.merge(record)
                for field, value in (changes or {}).items():
                    setattr(merged, field, value)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            await session.refresh(merged)
            return merged

    @classmethod
    async def delete(cls, record: Any) -> None:
        """Delete a record loaded earlier and commit."""
        async with cls.new_session() as session:
            try:
                await session.delete(await session.merge(record))
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @classmethod
    async def check_connection(cls) -> None:
        """Run SELECT 1 for /health; raises when the database is unreachable."""
        async with cls.new_session() as session:
            await session.execute(text("SELECT 1"))
