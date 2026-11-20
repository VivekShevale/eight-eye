from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import Conflict, Unauthorized

from app.config import settings
from app.models.user import User
from app.schemas.auth_schema import CurrentUserResponse, LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.db_service import DBService
from app.utils.auth_utils import AuthUtils
from app.utils.log_utils import LogUtils

logger = LogUtils.get_logger(__name__)


class AuthHelper:
    """Registration and login."""

    @staticmethod
    def register_user(payload: RegisterRequest) -> tuple[dict, int]:
        """Create an account; the duplicate check runs before the expensive hashing."""
        email = payload.email.lower()
        if DBService.read(select(exists().where(User.email == email)), one=True):
            raise Conflict("Email is already registered.")
        try:
            user = DBService.create(User(email=email, password_hash=AuthUtils.hash_password(payload.password)))
        except IntegrityError as exc:
            # Two registrations with the same email at the same time; the unique constraint caught it.
            raise Conflict("Email is already registered.") from exc
        logger.info("User registered | user_id=%s", user.id)
        return UserResponse.model_validate(user).model_dump(mode="json"), 201

    @staticmethod
    def login_user(payload: LoginRequest) -> tuple[dict, int]:
        """Return an access token; one generic message for unknown email and wrong password."""
        user = DBService.read(select(User).where(User.email == payload.email.lower()), one=True)
        if user is None or not AuthUtils.verify_password(payload.password, user.password_hash):
            logger.warning("Login rejected | reason=invalid_credentials")
            raise Unauthorized("Invalid email or password.")
        logger.info("User logged in | user_id=%s", user.id)
        response = TokenResponse(access_token=AuthUtils.create_token(user.id), expires_in=settings.access_token_expire_minutes * 60)
        return response.model_dump(mode="json"), 200

    @staticmethod
    def get_current_user() -> tuple[dict, int]:
        """The authenticated user, shaped by CurrentUserResponse."""
        return CurrentUserResponse(**AuthUtils.get_current_user()).model_dump(mode="json"), 200
