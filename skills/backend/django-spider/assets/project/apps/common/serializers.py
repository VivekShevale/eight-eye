from rest_framework import serializers


class HealthResponseSerializer(serializers.Serializer):
    """Response schema for GET /health/."""

    status = serializers.CharField()
    database = serializers.CharField()
