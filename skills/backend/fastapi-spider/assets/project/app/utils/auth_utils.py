import asyncio
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.config import settings
from app.models.user import User
from app.services.db_service import DBService

bearer_scheme = HTTPBearer(auto_error=False)


class AuthUtils:
    """Password hashing, JWT handling and the current-user dependency."""

    BCRYPT_ROUNDS = 12

    @classmethod
    async def hash_password(cls, password: str) -> str:
        """Hash a password in a worker thread so the event loop isn't blocked."""
        hashed = await asyncio.to_thread(bcrypt.hashpw, password.encode("utf-8"), bcrypt.gensalt(rounds=cls.BCRYPT_ROUNDS))
        return hashed.decode("utf-8")

    @staticmethod
    async def verify_password(password: str, password_hash: str) -> bool:
        """Check a password against its bcrypt hash in a worker thread."""
        return await asyncio.to_thread(bcrypt.checkpw, password.encode("utf-8"), password_hash.encode("utf-8"))

    @staticmethod
    def create_access_token(user_id: int | str) -> str:
        """Create a signed, short-lived access token for the user."""
        now = datetime.now(timezone.utc)
        payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.access_token_expire_minutes)}
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def decode_access_token(token: str) -> dict:
        """Verify a token and return its claims; any problem is a 401."""
        try:
            return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], options={"require": ["sub", "exp", "iat"]})
        except jwt.InvalidTokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.", headers={"WWW-Authenticate": "Bearer"}) from exc

    @classmethod
    async def get_current_user(cls, credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
        """FastAPI dependency: return the authenticated user, or raise 401."""
        if credentials is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.", headers={"WWW-Authenticate": "Bearer"})
        claims = cls.decode_access_token(credentials.credentials)
        user = await DBService.read(select(User).where(User.id == int(claims["sub"])), one=True)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.", headers={"WWW-Authenticate": "Bearer"})
        return {"user_id": user.id, "email": user.email}
