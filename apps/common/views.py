"""System views for common operations like health checks and global error handlers."""
import logging
from django.db import connection
from django.http import JsonResponse
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Liveness and readiness health check endpoint."""
    try:
        # Check database connectivity
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
    except Exception as exc:
        logger.error("Health check failed on database query: %s", exc)
        return Response(
            {
                "error": {
                    "code": "service_unavailable",
                    "message": "Database connectivity check failed.",
                }
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def custom_404_view(request, exception=None):
    """Global JSON 404 handler for unrouted paths."""
    return JsonResponse(
        {
            "error": {
                "code": "not_found",
                "message": "The requested resource was not found on this server.",
            }
        },
        status=status.HTTP_404_NOT_FOUND,
    )


def custom_500_view(request):
    """Global JSON 500 handler for unhandled exceptions."""
    return JsonResponse(
        {
            "error": {
                "code": "server_error",
                "message": "An unexpected server error occurred.",
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
