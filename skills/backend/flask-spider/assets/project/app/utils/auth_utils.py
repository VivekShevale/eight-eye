from flask_jwt_extended import create_access_token, current_user
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from app.models.user import User
from app.services.db_service import DBService


class AuthUtils:
    """Password hashing, token creation and the current user."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password with werkzeug's default algorithm."""
        return generate_password_hash(password)

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Check a password against its hash."""
        return check_password_hash(password_hash, password)

    @staticmethod
    def create_token(user_id: int) -> str:
        """Create an access token; the identity must be a string."""
        return create_access_token(identity=str(user_id))

    @staticmethod
    def load_user(jwt_header: dict, jwt_data: dict) -> User | None:
        """Flask-JWT-Extended user lookup: a token for a deleted user is rejected with 401."""
        return DBService.read(select(User).where(User.id == int(jwt_data["sub"])), one=True)

    @staticmethod
    def get_current_user() -> dict:
        """The authenticated user of this request (inside @jwt_required routes)."""
        return {"user_id": current_user.id, "email": current_user.email}

    @staticmethod
    def get_current_user_id() -> int:
        """The authenticated user's id; never taken from the request body."""
        return current_user.id
