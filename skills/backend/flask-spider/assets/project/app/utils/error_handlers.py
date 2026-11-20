from typing import Any

from flask import Flask, request
from flask_jwt_extended import JWTManager
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from werkzeug.exceptions import HTTPException

from app.schemas.common_schema import ErrorResponse
from app.utils.log_utils import LogUtils
from app.utils.request_utils import RequestValidationError

logger = LogUtils.get_logger(__name__)


class ErrorHandlers:
    """Turn every exception into the shared ErrorResponse with the right status code."""

    @staticmethod
    def build_response(status_code: int, message: str, details: list[dict[str, Any]] | None = None) -> tuple[dict, int]:
        """Build an error body in the shared format."""
        return ErrorResponse(message=message, details=details).model_dump(mode="json", exclude_none=True), status_code

    @staticmethod
    def build_auth_response(message: str) -> tuple[dict, int, dict]:
        """401 for token problems, with the WWW-Authenticate header clients expect."""
        body, status_code = ErrorHandlers.build_response(401, message)
        return body, status_code, {"WWW-Authenticate": "Bearer"}

    @staticmethod
    def handle_http_exception(exc: HTTPException) -> tuple[dict, int]:
        """Expected errors raised by helpers (NotFound, Conflict, ...) and Flask's own 404/405."""
        log = logger.error if (exc.code or 500) >= 500 else logger.warning
        log("HTTP error | method=%s | path=%s | status=%s", request.method, request.path, exc.code)
        return ErrorHandlers.build_response(exc.code or 500, exc.description or "Request failed.")

    @staticmethod
    def handle_request_validation(exc: RequestValidationError) -> tuple[dict, int]:
        """Invalid body or query parameters; never echoes the submitted values."""
        logger.warning("Request validation failed | method=%s | path=%s | fields=%s", request.method, request.path, len(exc.details))
        return ErrorHandlers.build_response(400, "Request validation failed.", exc.details)

    @staticmethod
    def handle_database_exception(exc: Exception) -> tuple[dict, int]:
        """Database unreachable."""
        logger.error("Database unavailable | path=%s | error_type=%s", request.path, type(exc).__name__)
        return ErrorHandlers.build_response(424, "Database dependency is unavailable.")

    @staticmethod
    def handle_pool_timeout(exc: PoolTimeoutError) -> tuple[dict, int]:
        """No free database connection within DB_POOL_TIMEOUT."""
        logger.error("Database pool exhausted | path=%s", request.path)
        return ErrorHandlers.build_response(503, "The service is busy. Please try again shortly.")

    @staticmethod
    def handle_unexpected_exception(exc: Exception) -> tuple[dict, int]:
        """Anything unexpected: traceback to the log, generic message to the client."""
        logger.exception("Unexpected error | method=%s | path=%s", request.method, request.path)
        return ErrorHandlers.build_response(500, "An unexpected error occurred.")

    @staticmethod
    def handle_missing_token(reason: str) -> tuple[dict, int, dict]:
        """No Authorization header."""
        logger.warning("Authentication failed | path=%s | reason=missing_token", request.path)
        return ErrorHandlers.build_auth_response("Not authenticated.")

    @staticmethod
    def handle_invalid_token(reason: str) -> tuple[dict, int, dict]:
        """Malformed or tampered token."""
        logger.warning("Authentication failed | path=%s | reason=invalid_token", request.path)
        return ErrorHandlers.build_auth_response("Invalid or expired token.")

    @staticmethod
    def handle_expired_token(jwt_header: dict, jwt_payload: dict) -> tuple[dict, int, dict]:
        """Expired token."""
        logger.warning("Authentication failed | path=%s | reason=expired_token", request.path)
        return ErrorHandlers.build_auth_response("Invalid or expired token.")

    @staticmethod
    def handle_user_lookup_error(jwt_header: dict, jwt_payload: dict) -> tuple[dict, int, dict]:
        """Valid token for a user that no longer exists."""
        logger.warning("Authentication failed | path=%s | reason=user_not_found", request.path)
        return ErrorHandlers.build_auth_response("Invalid or expired token.")

    @staticmethod
    def register_handlers(app: Flask, jwt: JWTManager) -> None:
        """Register every handler once, from create_app()."""
        app.register_error_handler(HTTPException, ErrorHandlers.handle_http_exception)
        app.register_error_handler(RequestValidationError, ErrorHandlers.handle_request_validation)
        app.register_error_handler(OperationalError, ErrorHandlers.handle_database_exception)
        app.register_error_handler(PoolTimeoutError, ErrorHandlers.handle_pool_timeout)
        app.register_error_handler(Exception, ErrorHandlers.handle_unexpected_exception)
        # Flask-JWT-Extended answers auth failures itself; these loaders give them the shared shape.
        jwt.unauthorized_loader(ErrorHandlers.handle_missing_token)
        jwt.invalid_token_loader(ErrorHandlers.handle_invalid_token)
        jwt.expired_token_loader(ErrorHandlers.handle_expired_token)
        jwt.user_lookup_error_loader(ErrorHandlers.handle_user_lookup_error)
