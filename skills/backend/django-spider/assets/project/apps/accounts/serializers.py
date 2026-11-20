from password_validator import PasswordValidator
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import User

PASSWORD_SCHEMA = PasswordValidator().min(8).max(100).has().uppercase().has().lowercase().has().digits().has().symbols().has().no().spaces()


class RegisterSerializer(serializers.Serializer):
    """Registration input; the password policy lives here only, never at login."""

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=100, trim_whitespace=False)

    def validate_password(self, value: str) -> str:
        """Enforce the password policy with the password-validator library."""
        if not PASSWORD_SCHEMA.validate(value):
            raise serializers.ValidationError("Password must be 8-100 characters with upper and lower case letters, a digit, a symbol and no spaces.")
        return value


class LoginSerializer(TokenObtainPairSerializer):
    """SimpleJWT login with one generic message for unknown email and wrong password."""

    default_error_messages = {"no_active_account": "Invalid email or password."}


class UserSerializer(serializers.ModelSerializer):
    """Public user data."""

    class Meta:
        model = User
        fields = ("id", "email", "role")
        read_only_fields = fields
