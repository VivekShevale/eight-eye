from django.db import connection


class HealthHelper:
    """Report whether the app and its database work."""

    @staticmethod
    def check_health() -> dict:
        """Run SELECT 1; a failure reaches the exception handler and becomes 424."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return {"status": "ok", "database": "ok"}
