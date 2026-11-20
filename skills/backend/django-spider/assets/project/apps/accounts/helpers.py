import logging

from django.db import IntegrityError

from apps.accounts.models import User
from apps.common.error_handlers import ConflictError

logger = logging.getLogger(__name__)


class AccountHelper:
    """Account business logic."""

    @staticmethod
    def register_user(validated_data: dict) -> User:
        """Create a customer account; the duplicate check runs before the expensive hashing."""
        email = validated_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise ConflictError("Email is already registered.")
        try:
            user = User.objects.create_user(email=email, password=validated_data["password"])
        except IntegrityError as exc:
            # Two registrations with the same email at the same time; the unique constraint caught it.
            raise ConflictError("Email is already registered.") from exc
        logger.info("User registered | user_id=%s", user.id)
        return user
