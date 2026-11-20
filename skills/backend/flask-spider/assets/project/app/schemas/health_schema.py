from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Application and dependency status."""

    status: str
    database: str
