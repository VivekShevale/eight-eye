from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Create users identified by email instead of username."""

    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        """Create a regular user with a hashed password."""
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        """Create an administrator with Django admin access."""
        extra_fields.update(is_staff=True, is_superuser=True, role=User.Role.ADMINISTRATOR)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Account identified by email, with an application role. Created before the first migration."""

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        AGENT = "agent", "Support agent"
        ADMINISTRATOR = "administrator", "Administrator"

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        return self.email
