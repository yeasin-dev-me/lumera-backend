"""Domain models for transactional customer notifications and preferences (ADR-0015, ADR-0018)."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.common.models import PublicIdModel, TimeStampedModel


class Notification(PublicIdModel, TimeStampedModel):
    """Transactional customer notification audit record."""

    CHANNEL_EMAIL = "email"
    CHANNEL_SMS = "sms"
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_SMS, "SMS"),
    ]

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    # Controlled notification taxonomy
    EVENT_ORDER_PLACED = "order_placed"
    EVENT_PAYMENT_CONFIRMED = "payment_confirmed"
    EVENT_PAYMENT_FAILED = "payment_failed"
    EVENT_ORDER_PROCESSING = "order_processing"
    EVENT_ORDER_SHIPPED = "order_shipped"
    EVENT_ORDER_DELIVERED = "order_delivered"
    EVENT_ORDER_CANCELLED = "order_cancelled"
    EVENT_RETURN_REQUESTED = "return_requested"
    EVENT_RETURN_APPROVED = "return_approved"
    EVENT_RETURN_REJECTED = "return_rejected"
    EVENT_RETURN_RECEIVED = "return_received"
    EVENT_REFUND_INITIATED = "refund_initiated"
    EVENT_REFUND_COMPLETED = "refund_completed"
    EVENT_ACCOUNT_WELCOME = "account_welcome"

    EVENT_CHOICES = [
        (EVENT_ORDER_PLACED, "Order Placed"),
        (EVENT_PAYMENT_CONFIRMED, "Payment Confirmed"),
        (EVENT_PAYMENT_FAILED, "Payment Failed"),
        (EVENT_ORDER_PROCESSING, "Order Processing"),
        (EVENT_ORDER_SHIPPED, "Order Shipped"),
        (EVENT_ORDER_DELIVERED, "Order Delivered"),
        (EVENT_ORDER_CANCELLED, "Order Cancelled"),
        (EVENT_RETURN_REQUESTED, "Return Requested"),
        (EVENT_RETURN_APPROVED, "Return Approved"),
        (EVENT_RETURN_REJECTED, "Return Rejected"),
        (EVENT_RETURN_RECEIVED, "Return Received"),
        (EVENT_REFUND_INITIATED, "Refund Initiated"),
        (EVENT_REFUND_COMPLETED, "Refund Completed"),
        (EVENT_ACCOUNT_WELCOME, "Account Welcome"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    return_request = models.ForeignKey(
        "orders.ReturnRequest",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    refund = models.ForeignKey(
        "payments.Refund",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )

    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True, default="")
    event_type = models.CharField(max_length=64, choices=EVENT_CHOICES)
    channel = models.CharField(max_length=32, choices=CHANNEL_CHOICES, default=CHANNEL_EMAIL)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    attempt_count = models.PositiveIntegerField(default=1)
    provider_message_id = models.CharField(max_length=255, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_notification"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "event_type"],
                condition=Q(order__isnull=False),
                name="unique_order_event_notification",
            ),
            models.UniqueConstraint(
                fields=["return_request", "event_type"],
                condition=Q(return_request__isnull=False),
                name="unique_return_event_notification",
            ),
            models.UniqueConstraint(
                fields=["refund", "event_type"],
                condition=Q(refund__isnull=False),
                name="unique_refund_event_notification",
            ),
            models.UniqueConstraint(
                fields=["user", "event_type"],
                condition=Q(user__isnull=False, event_type="account_welcome"),
                name="unique_user_welcome_notification",
            ),
        ]

    def __str__(self):
        return f"{self.channel.upper()} {self.event_type} -> {self.recipient} ({self.status})"


class CommunicationPreference(PublicIdModel, TimeStampedModel):
    """Customer communication consent and operational preference settings (BR-31, ADR-0018)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="communication_preferences",
    )
    marketing_email = models.BooleanField(
        default=False,
        help_text="Opt-in consent for promotional and marketing emails.",
    )
    marketing_sms = models.BooleanField(
        default=False,
        help_text="Opt-in consent for promotional SMS messages.",
    )
    order_updates_email = models.BooleanField(
        default=True,
        help_text="Operational order status and payment updates (always True).",
    )

    class Meta:
        db_table = "notifications_communicationpreference"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Preferences for {self.user.email} (marketing={self.marketing_email})"
