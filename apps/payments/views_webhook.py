"""Webhook and IPN callback views for Payment Gateways (ADR-0014)."""
import logging
from django.views.decorators.csrf import csrf_exempt
from rest_framework import parsers, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .services import process_gateway_callback

logger = logging.getLogger(__name__)


class PaymentWebhookView(APIView):
    """POST /api/v1/internal/payments/webhook/{gateway}/
    POST /api/v1/payments/webhook/{gateway}/
    
    Server-to-server gateway callback endpoint.
    Protected by gateway verification protocol and signature/validator checks.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    parser_classes = [parsers.JSONParser, parsers.FormParser, parsers.MultiPartParser]

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, gateway: str):
        payload = {}
        if isinstance(request.data, dict):
            payload.update(request.data)
        elif hasattr(request.data, "dict"):
            payload.update(request.data.dict())

        # Also merge query parameters in case gateway passed parameters in query string
        if request.query_params:
            payload.update(request.query_params.dict())

        logger.info("Received payment callback for gateway '%s'", gateway)

        result = process_gateway_callback(gateway_id=gateway, payload=payload)

        res_status = result.get("status")
        if res_status in ("paid", "already_paid"):
            return Response(result, status=status.HTTP_200_OK)
        elif res_status == "failed":
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, gateway: str):
        """Handle GET redirect returns from payment gateways."""
        payload = request.query_params.dict()
        result = process_gateway_callback(gateway_id=gateway, payload=payload)
        return Response(result, status=status.HTTP_200_OK)
