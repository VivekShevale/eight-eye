from django.http import JsonResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.error_handlers import ErrorHandlers
from apps.common.helpers import HealthHelper
from apps.common.serializers import HealthResponseSerializer


class HealthView(APIView):
    """GET /health/: 200 when the database answers, 424 when it doesn't."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(HealthResponseSerializer(HealthHelper.check_health()).data)


def page_not_found(request, exception):
    """handler404: unknown URLs get JSON in the shared shape."""
    return JsonResponse(ErrorHandlers.build_body("Resource not found."), status=404)


def server_error(request):
    """handler500: errors outside DRF views get JSON in the shared shape."""
    return JsonResponse(ErrorHandlers.build_body("An unexpected error occurred."), status=500)
