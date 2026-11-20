from password_validator import PasswordValidator
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PASSWORD_SCHEMA = PasswordValidator().min(8).max(72).has().uppercase().has().lowercase().has().digits().has().symbols().has().no().spaces()


class RegisterRequest(BaseModel):
    """Registration payload; the password policy applies here only, never at login."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(max_length=72)

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, value: str) -> str:
        """Enforce the password policy with the password-validator library."""
        if len(value.encode("utf-8")) > 72 or not PASSWORD_SCHEMA.validate(value):
            raise ValueError("Password must be 8-72 characters with upper and lower case letters, a digit, a symbol and no spaces.")
        return value


class LoginRequest(BaseModel):
    """Login payload."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserResponse(BaseModel):
    """Public user data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr


class CurrentUserResponse(BaseModel):
    """The authenticated user, as returned by AuthUtils.get_current_user."""

    user_id: int
    email: EmailStr


class TokenResponse(BaseModel):
    """Access token returned after login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
