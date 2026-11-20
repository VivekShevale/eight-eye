import logging
from typing import Any

from django.db import InterfaceError, OperationalError
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ConflictError(APIException):
    """409 for duplicates; DRF has no built-in conflict exception."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "The resource already exists."
    default_code = "conflict"


class ErrorHandlers:
    """Give every API error the shared shape: {"status": "error", "message": ..., "details": [...]}."""

    @staticmethod
    def build_body(message: str, details: list[dict[str, str]] | None = None) -> dict[str, Any]:
        """Error body in the shared format; details only when there are field errors."""
        body: dict[str, Any] = {"status": "error", "message": message}
        if details:
            body["details"] = details
        return body

    @classmethod
    def flatten_errors(cls, errors: Any, prefix: str = "") -> list[dict[str, str]]:
        """Turn DRF's nested error dicts and lists into [{"field": ..., "message": ...}]."""
        if isinstance(errors, dict):
            details = []
            for field, value in errors.items():
                details.extend(cls.flatten_errors(value, f"{prefix}.{field}" if prefix else str(field)))
            return details
        if isinstance(errors, list):
            details = []
            for index, value in enumerate(errors):
                nested_prefix = f"{prefix}.{index}" if isinstance(value, (dict, list)) else prefix
                details.extend(cls.flatten_errors(value, nested_prefix))
            return details
        return [{"field": prefix or "non_field_errors", "message": str(errors)}]

    @staticmethod
    def extract_message(data: Any) -> str:
        """The human-readable message DRF put in its default response."""
        if isinstance(data, dict) and "detail" in data:
            return str(data["detail"])
        return "Request failed."

    @classmethod
    def handle_exception(cls, exc: Exception, context: dict) -> Response:
        """DRF EXCEPTION_HANDLER: shared shape for every error raised in an API view."""
        request = context.get("request")
        path = request.path if request else ""
        if isinstance(exc, (OperationalError, InterfaceError)):
            logger.error("Database unavailable | path=%s | error_type=%s", path, type(exc).__name__)
            return Response(cls.build_body("Database dependency is unavailable."), status=status.HTTP_424_FAILED_DEPENDENCY)
        response = exception_handler(exc, context)
        if response is None:
            logger.exception("Unexpected error | path=%s", path)
            return Response(cls.build_body("An unexpected error occurred."), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if isinstance(exc, ValidationError):
            details = cls.flatten_errors(exc.detail)
            logger.warning("Request validation failed | path=%s | fields=%s", path, len(details))
            response.data = cls.build_body("Request validation failed.", details)
            return response
        logger.warning("HTTP error | path=%s | status=%s", path, response.status_code)
        response.data = cls.build_body(cls.extract_message(response.data))
        return response


# DRF imports the handler by dotted path, which must point at a module-level name.
handle_exception = ErrorHandlers.handle_exception
