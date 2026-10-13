"""Customer-facing views for Payment Initiation and Status (ADR-0014)."""
import uuid
from django.db.models import Q
from rest_framework import exceptions, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.cart.serializers import format_money
from apps.orders.models import Order
from .models import Payment
from .serializers import (
    PaymentInitiateInputSerializer,
    PaymentInitiateResponseSerializer,
    PaymentStatusSerializer,
)
from .services import initiate_payment


class CustomerOrderPaymentView(APIView):
    """POST /api/v1/customer/orders/{public_id}/payment/ - Initiate payment session.
    GET /api/v1/customer/orders/{public_id}/payment/ - Retrieve authoritative payment status.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, public_id):
        serializer = PaymentInitiateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        gateway_id = serializer.validated_data.get("gateway", "sslcommerz")
        return_url = serializer.validated_data.get("return_url", "")

        user = request.user if request.user.is_authenticated else None

        payment, init_res = initiate_payment(
            user=user,
            order_public_id=public_id,
            gateway_id=gateway_id,
            return_url=return_url,
        )

        response_data = {
            "payment_public_id": payment.public_id,
            "order_public_id": payment.order.public_id,
            "order_number": payment.order.order_number,
            "gateway": payment.gateway,
            "amount": format_money(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
            "redirect_url": init_res.get("redirect_url", ""),
            "provider_reference": payment.provider_reference,
        }
        resp_serializer = PaymentInitiateResponseSerializer(response_data)
        return Response(resp_serializer.data, status=status.HTTP_201_CREATED)

    def get(self, request, public_id):
        try:
            val_uuid = uuid.UUID(str(public_id))
        except (ValueError, TypeError):
            raise exceptions.NotFound("Order not found.")

        # Customer isolation
        if request.user.is_authenticated:
            order = Order.objects.filter(
                Q(user=request.user) | Q(user__isnull=True),
                public_id=val_uuid,
            ).first()
        else:
            order = Order.objects.filter(user__isnull=True, public_id=val_uuid).first()

        if not order:
            raise exceptions.NotFound("Order not found.")

        payment = (
            Payment.objects.filter(order=order)
            .prefetch_related("attempts")
            .order_by("-created_at")
            .first()
        )

        if not payment:
            return Response(
                {
                    "payment_public_id": None,
                    "order_public_id": str(order.public_id),
                    "order_number": order.order_number,
                    "status": "pending",
                    "amount": format_money(order.total),
                    "currency": order.currency,
                    "gateway": "sslcommerz",
                    "method": "",
                    "provider_transaction_id": "",
                    "paid_at": None,
                    "attempts": [],
                },
                status=status.HTTP_200_OK,
            )

        serializer = PaymentStatusSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)
