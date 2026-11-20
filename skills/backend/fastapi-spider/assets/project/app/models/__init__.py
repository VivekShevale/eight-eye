from app.models.base import Base
from app.models.expense import Expense
from app.models.user import User

# Importing every model here registers it on Base.metadata for Alembic autogenerate.
__all__ = ["Base", "Expense", "User"]
