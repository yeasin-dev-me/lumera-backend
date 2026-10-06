"""Domain models for transactional notifications (ADR-0015)."""
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

    EVENT_ORDER_PLACED = "order_placed"
    EVENT_PAYMENT_CONFIRMED = "payment_confirmed"
    EVENT_ORDER_PROCESSING = "order_processing"
    EVENT_ORDER_SHIPPED = "order_shipped"
    EVENT_ORDER_DELIVERED = "order_delivered"
    EVENT_ORDER_CANCELLED = "order_cancelled"
    EVENT_CHOICES = [
        (EVENT_ORDER_PLACED, "Order Placed"),
        (EVENT_PAYMENT_CONFIRMED, "Payment Confirmed"),
        (EVENT_ORDER_PROCESSING, "Order Processing"),
        (EVENT_ORDER_SHIPPED, "Order Shipped"),
        (EVENT_ORDER_DELIVERED, "Order Delivered"),
        (EVENT_ORDER_CANCELLED, "Order Cancelled"),
    ]

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    recipient = models.CharField(max_length=255)
    event_type = models.CharField(max_length=64, choices=EVENT_CHOICES)
    channel = models.CharField(max_length=32, choices=CHANNEL_CHOICES, default=CHANNEL_EMAIL)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "notifications_notification"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "event_type"],
                condition=Q(order__isnull=False),
                name="unique_order_event_notification",
            )
        ]

    def __str__(self):
        return f"{self.channel.upper()} {self.event_type} -> {self.recipient} ({self.status})"
