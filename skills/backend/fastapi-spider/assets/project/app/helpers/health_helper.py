from app.schemas.health_schema import HealthResponse
from app.services.db_service import DBService


class HealthHelper:
    """Report whether the app and its dependencies work."""

    @staticmethod
    async def check_health() -> HealthResponse:
        """Ping the database; a failure reaches ErrorHandlers and becomes 424."""
        await DBService.check_connection()
        return HealthResponse(status="ok", database="ok")
