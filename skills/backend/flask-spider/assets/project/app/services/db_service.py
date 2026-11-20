from typing import Any

from sqlalchemy import Select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.extensions import db


class DBService:
    """Run every database operation in its own short session on Flask-SQLAlchemy's engine.

    Flask-SQLAlchemy owns the engine and pool (SQLALCHEMY_ENGINE_OPTIONS); its request-scoped
    db.session is not used, so no connection stays checked out while a request does slow work.
    """

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

    @staticmethod
    def new_session() -> Session:
        """Return a new short-lived session bound to the app's engine."""
        return Session(db.engine, expire_on_commit=False, autoflush=False)

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
