"""Domain models for Payments and Payment Attempts (ADR-0014, BR-12)."""
from decimal import Decimal
from django.db import models
from django.db.models import Q
from apps.common.models import PublicIdModel, TimeStampedModel


class Payment(PublicIdModel, TimeStampedModel):
    """Authoritative payment record for an Order (ADR-0014)."""

    STATUS_PENDING = "pending"
    STATUS_INITIATED = "initiated"
    STATUS_PROCESSING = "processing"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_REFUNDED = "refunded"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_INITIATED, "Initiated"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    gateway = models.CharField(max_length=64, default="sslcommerz", db_index=True)
    method = models.CharField(max_length=64, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    provider_transaction_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    provider_reference = models.CharField(max_length=255, blank=True, default="", db_index=True)
    idempotency_key = models.CharField(max_length=255, blank=True, default="", db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payments_payment"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                check=Q(amount__gt=Decimal("0.00")),
                name="check_payment_amount_positive",
            ),
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(status="paid"),
                name="unique_paid_payment_per_order",
            ),
        ]

    def __str__(self):
        return f"Payment {self.public_id} ({self.gateway}: {self.status}) for Order {self.order.order_number}"


class PaymentAttempt(PublicIdModel, TimeStampedModel):
    """Audit record of an individual gateway interaction/attempt (ADR-0014)."""

    STATUS_INITIATED = "initiated"
    STATUS_PROCESSING = "processing"
    STATUS_SUCCESSFUL = "successful"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    ATTEMPT_STATUS_CHOICES = [
        (STATUS_INITIATED, "Initiated"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SUCCESSFUL, "Successful"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payment_attempts",
    )
    attempt_number = models.PositiveIntegerField(default=1)
    gateway = models.CharField(max_length=64)
    provider_reference = models.CharField(max_length=255, blank=True, default="")
    provider_transaction_id = models.CharField(max_length=255, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(
        max_length=32,
        choices=ATTEMPT_STATUS_CHOICES,
        default=STATUS_INITIATED,
    )
    error_message = models.TextField(blank=True, default="")
    raw_response = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payments_paymentattempt"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Attempt #{self.attempt_number} for Payment {self.payment.public_id} ({self.status})"
