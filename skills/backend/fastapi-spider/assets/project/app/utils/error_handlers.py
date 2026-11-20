from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common_schema import ErrorResponse
from app.utils.log_utils import LogUtils

logger = LogUtils.get_logger(__name__)


class ErrorHandlers:
    """Turn every exception into the shared ErrorResponse with the right status code."""

    @staticmethod
    def build_response(status_code: int, message: str, details: list[dict[str, Any]] | None = None, headers: dict | None = None) -> JSONResponse:
        """Build a JSON error response in the shared format."""
        content = ErrorResponse(message=message, details=details).model_dump(mode="json", exclude_none=True)
        return JSONResponse(status_code=status_code, content=content, headers=headers)

    @staticmethod
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Expected errors raised by helpers (400, 401, 404, 409, ...)."""
        log = logger.error if exc.status_code >= 500 else logger.warning
        log("HTTP error | method=%s | path=%s | status=%s", request.method, request.url.path, exc.status_code)
        return ErrorHandlers.build_response(exc.status_code, str(exc.detail), headers=getattr(exc, "headers", None))

    @staticmethod
    async def handle_validation_exception(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Schema validation failures; never echoes the submitted values."""
        details = [{"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]} for error in exc.errors()]
        logger.warning("Request validation failed | method=%s | path=%s | fields=%s", request.method, request.url.path, len(details))
        return ErrorHandlers.build_response(422, "Request validation failed.", details)

    @staticmethod
    async def handle_database_exception(request: Request, exc: Exception) -> JSONResponse:
        """Database unreachable or not configured."""
        logger.error("Database unavailable | path=%s | error_type=%s", request.url.path, type(exc).__name__)
        return ErrorHandlers.build_response(424, "Database dependency is unavailable.")

    @staticmethod
    async def handle_pool_timeout(request: Request, exc: PoolTimeoutError) -> JSONResponse:
        """No free database connection within DB_POOL_TIMEOUT."""
        logger.error("Database pool exhausted | path=%s", request.url.path)
        return ErrorHandlers.build_response(503, "The service is busy. Please try again shortly.")

    @staticmethod
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        """Anything unexpected: full traceback to the log, generic message to the client."""
        logger.exception("Unexpected error | method=%s | path=%s", request.method, request.url.path)
        return ErrorHandlers.build_response(500, "An unexpected error occurred.")

    @staticmethod
    def register_handlers(app: FastAPI) -> None:
        """Register every handler once, from main.py."""
        app.add_exception_handler(StarletteHTTPException, ErrorHandlers.handle_http_exception)
        app.add_exception_handler(RequestValidationError, ErrorHandlers.handle_validation_exception)
        # MongoDB projects: register pymongo.errors.ConnectionFailure here instead of OperationalError.
        app.add_exception_handler(OperationalError, ErrorHandlers.handle_database_exception)
        app.add_exception_handler(ConnectionError, ErrorHandlers.handle_database_exception)
        app.add_exception_handler(PoolTimeoutError, ErrorHandlers.handle_pool_timeout)
        app.add_exception_handler(Exception, ErrorHandlers.handle_unexpected_exception)
