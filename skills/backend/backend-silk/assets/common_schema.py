from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Common schema for every API error response."""

    status: str = "error"
    message: str
    details: list[dict[str, Any]] | None = None
    # Set only when a client or another repo must branch on the error, e.g. "DATABASE_UNAVAILABLE".
    error_code: str | None = None
