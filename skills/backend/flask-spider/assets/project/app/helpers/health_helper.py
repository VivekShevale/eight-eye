from app.schemas.health_schema import HealthResponse
from app.services.db_service import DBService


class HealthHelper:
    """Report whether the app and its dependencies work."""

    @staticmethod
    def check_health() -> tuple[dict, int]:
        """Ping the database; a failure reaches ErrorHandlers and becomes 424."""
        DBService.check_connection()
        return HealthResponse(status="ok", database="ok").model_dump(), 200
