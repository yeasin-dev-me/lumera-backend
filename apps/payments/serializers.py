"""Serializers for Payments domain (ADR-0014)."""
from rest_framework import serializers
from apps.cart.serializers import format_money
from .models import Payment, PaymentAttempt, Refund


class PaymentAttemptSerializer(serializers.ModelSerializer):
    """Attempt log detail for audit trail."""

    amount = serializers.SerializerMethodField()

    class Meta:
        model = PaymentAttempt
        fields = [
            "public_id",
            "attempt_number",
            "gateway",
            "status",
            "amount",
            "currency",
            "provider_reference",
            "provider_transaction_id",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields

    def get_amount(self, obj: PaymentAttempt) -> str:
        return format_money(obj.amount)


class PaymentStatusSerializer(serializers.ModelSerializer):
    """Authoritative payment summary and attempt history."""

    payment_public_id = serializers.UUIDField(source="public_id", read_only=True)
    order_public_id = serializers.UUIDField(source="order.public_id", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    amount = serializers.SerializerMethodField()
    attempts = PaymentAttemptSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "payment_public_id",
            "order_public_id",
            "order_number",
            "status",
            "amount",
            "currency",
            "gateway",
            "method",
            "provider_transaction_id",
            "paid_at",
            "attempts",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_amount(self, obj: Payment) -> str:
        return format_money(obj.amount)


class PaymentInitiateInputSerializer(serializers.Serializer):
    """Input payload for payment initiation."""

    gateway = serializers.CharField(max_length=64, required=False, default="sslcommerz")
    return_url = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class PaymentInitiateResponseSerializer(serializers.Serializer):
    """Response returned upon successful payment session initiation."""

    payment_public_id = serializers.UUIDField()
    order_public_id = serializers.UUIDField()
    order_number = serializers.CharField()
    gateway = serializers.CharField()
    amount = serializers.CharField()
    currency = serializers.CharField()
    status = serializers.CharField()
    redirect_url = serializers.CharField()
    provider_reference = serializers.CharField()


class RefundSerializer(serializers.ModelSerializer):
    public_id = serializers.UUIDField(read_only=True)
    payment_public_id = serializers.UUIDField(source="payment.public_id", read_only=True)
    order_public_id = serializers.UUIDField(source="order.public_id", read_only=True)

    class Meta:
        model = Refund
        fields = [
            "public_id", "payment_public_id", "order_public_id", "amount",
            "currency", "status", "reason", "created_at",
        ]
        read_only_fields = [
            "public_id", "payment_public_id", "order_public_id",
            "currency", "status", "created_at",
        ]


class RefundCreateSerializer(serializers.Serializer):
    payment_public_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
