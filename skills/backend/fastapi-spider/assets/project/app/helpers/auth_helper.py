from fastapi import HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models.user import User
from app.schemas.auth_schema import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.db_service import DBService
from app.utils.auth_utils import AuthUtils
from app.utils.log_utils import LogUtils

logger = LogUtils.get_logger(__name__)


class AuthHelper:
    """Registration and login."""

    @staticmethod
    async def register_user(payload: RegisterRequest) -> UserResponse:
        """Create an account; the duplicate check runs before the expensive hashing."""
        email = payload.email.lower()
        if await DBService.read(select(exists().where(User.email == email)), one=True):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.")
        password_hash = await AuthUtils.hash_password(payload.password)
        try:
            user = await DBService.create(User(email=email, password_hash=password_hash))
        except IntegrityError as exc:
            # Two registrations with the same email at the same time; the unique constraint caught it.
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.") from exc
        logger.info("User registered | user_id=%s", user.id)
        return UserResponse.model_validate(user)

    @staticmethod
    async def login_user(payload: LoginRequest) -> TokenResponse:
        """Return an access token; one generic message for unknown email and wrong password."""
        user = await DBService.read(select(User).where(User.email == payload.email.lower()), one=True)
        if user is None or not await AuthUtils.verify_password(payload.password, user.password_hash):
            logger.warning("Login rejected | reason=invalid_credentials")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
        logger.info("User logged in | user_id=%s", user.id)
        return TokenResponse(access_token=AuthUtils.create_access_token(user.id), expires_in=settings.access_token_expire_minutes * 60)
