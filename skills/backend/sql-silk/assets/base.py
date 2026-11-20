from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Every index and constraint gets a predictable name, so migrations can drop them on downgrade
# and IntegrityError handlers can check e.g. "uq_users_email".
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all models. Flask-SQLAlchemy: db = SQLAlchemy(model_class=Base)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Timezone-aware creation and update times, set automatically."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)


class AuditMixin(TimestampMixin):
    """Timestamps plus who created and last updated the row (set from the token, never the request body)."""

    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


# Example model:
#
# class Expense(AuditMixin, Base):
#     """An expense owned by one user."""
#
#     __tablename__ = "expenses"
#     __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#     user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
#     title: Mapped[str] = mapped_column(String(200))
#     amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
#     category: Mapped[str] = mapped_column(String(50), index=True)
#     expense_date: Mapped[date] = mapped_column(Date, index=True)
#
#     # Three FKs point at users, so the relationship must say which one it uses.
#     user: Mapped["User"] = relationship(back_populates="expenses", foreign_keys=[user_id])
