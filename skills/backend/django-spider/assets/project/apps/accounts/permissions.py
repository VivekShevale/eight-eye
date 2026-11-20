from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsCustomer(BasePermission):
    """Only customers."""

    message = "Only customers can perform this action."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.role == User.Role.CUSTOMER)


class IsAdministrator(BasePermission):
    """Only administrators."""

    message = "Only administrators can perform this action."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.role == User.Role.ADMINISTRATOR)
