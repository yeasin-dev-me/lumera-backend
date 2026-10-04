"""Standardized exception handler for Lumera API."""
import logging
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """Transform DRF and unexpected exceptions into Lumera standard error format:
    {
      "error": {
        "code": "validation_error",
        "message": "...",
        "details": {...}
      }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_code = "error"
        message = "An error occurred."
        details = None

        if isinstance(exc, exceptions.ValidationError):
            error_code = "validation_error"
            message = "One or more fields are invalid."
            if isinstance(response.data, dict):
                details = {
                    key: val if isinstance(val, list) else [str(val)]
                    for key, val in response.data.items()
                }
            elif isinstance(response.data, list):
                details = {"non_field_errors": [str(item) for item in response.data]}
        elif isinstance(exc, exceptions.NotAuthenticated):
            error_code = "not_authenticated"
            message = getattr(exc, "detail", "Authentication credentials were not provided.")
        elif isinstance(exc, exceptions.AuthenticationFailed):
            error_code = "authentication_failed"
            message = getattr(exc, "detail", "Incorrect authentication credentials.")
        elif isinstance(exc, exceptions.PermissionDenied):
            error_code = "permission_denied"
            message = getattr(exc, "detail", "You do not have permission to perform this action.")
        elif isinstance(exc, exceptions.NotFound):
            error_code = "not_found"
            message = getattr(exc, "detail", "Resource not found.")
        elif isinstance(exc, exceptions.MethodNotAllowed):
            error_code = "method_not_allowed"
            message = getattr(exc, "detail", f"Method '{context.get('request').method}' not allowed.")
        elif isinstance(exc, exceptions.Throttled):
            error_code = "throttled"
            message = f"Request was throttled. Expected available in {exc.wait} seconds."
        else:
            if hasattr(exc, "default_code"):
                error_code = exc.default_code
            if hasattr(exc, "detail"):
                message = str(exc.detail)

        payload = {
            "error": {
                "code": error_code,
                "message": str(message),
            }
        }
        if details:
            payload["error"]["details"] = details

        response.data = payload
        return response

    # Unhandled server errors (500)
    logger.exception("Unhandled server exception: %s", exc)
    return Response(
        {
            "error": {
                "code": "server_error",
                "message": "An unexpected server error occurred.",
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
