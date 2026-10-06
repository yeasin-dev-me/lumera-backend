"""Transactional notification dispatch services with failure isolation (ADR-0015)."""
import logging
from typing import Any, Optional
from django.conf import settings
from django.core.mail import send_mail
from .models import Notification

logger = logging.getLogger(__name__)

EVENT_SUBJECT_MAP = {
    Notification.EVENT_ORDER_PLACED: "Order Confirmation: {order_number}",
    Notification.EVENT_PAYMENT_CONFIRMED: "Payment Confirmed for Order {order_number}",
    Notification.EVENT_ORDER_PROCESSING: "Your Order {order_number} is Being Prepared",
    Notification.EVENT_ORDER_SHIPPED: "Your Order {order_number} Has Shipped!",
    Notification.EVENT_ORDER_DELIVERED: "Your Order {order_number} Has Been Delivered",
    Notification.EVENT_ORDER_CANCELLED: "Order {order_number} Cancellation Notice",
}


def build_email_content(order, event_type: str) -> tuple[str, str]:
    """Return (subject, plain_text_body) for a given order lifecycle event."""
    order_num = getattr(order, "order_number", "")
    subject = EVENT_SUBJECT_MAP.get(
        event_type, f"Order Update: {order_num}"
    ).format(order_number=order_num)

    lines = [
        f"Hello {getattr(order, 'shipping_full_name', 'Customer')},",
        "",
    ]

    if event_type == Notification.EVENT_ORDER_PLACED:
        lines.append(f"Thank you for placing order {order_num}. Total: {order.total} {order.currency}.")
    elif event_type == Notification.EVENT_PAYMENT_CONFIRMED:
        lines.append(f"We have successfully received payment for your order {order_num}.")
    elif event_type == Notification.EVENT_ORDER_PROCESSING:
        lines.append(f"Your order {order_num} has entered processing at our warehouse.")
    elif event_type == Notification.EVENT_ORDER_SHIPPED:
        lines.append(f"Great news! Your order {order_num} has shipped.")
        if getattr(order, "courier", None):
            lines.append(f"Courier: {order.courier}")
        if getattr(order, "tracking_number", None):
            lines.append(f"Tracking Number: {order.tracking_number}")
        if getattr(order, "tracking_url", None):
            lines.append(f"Track Online: {order.tracking_url}")
    elif event_type == Notification.EVENT_ORDER_DELIVERED:
        lines.append(f"Your order {order_num} has been successfully delivered. Thank you for shopping with Lumera!")
    elif event_type == Notification.EVENT_ORDER_CANCELLED:
        lines.append(f"Your order {order_num} has been cancelled.")
    else:
        lines.append(f"There is an update on your order {order_num}.")

    lines.extend([
        "",
        "Best regards,",
        "The Lumera Team",
    ])
    return subject, "\n".join(lines)


def send_order_notification(order, event_type: str, metadata: Optional[dict[str, Any]] = None) -> Optional[Notification]:
    """Dispatches order event notification with failure isolation and idempotency (ADR-0015).
    
    1. Idempotency check: if an event notification already exists for this order, do not duplicate.
    2. Persist Notification record.
    3. Attempt email dispatch via configured Django EmailBackend.
    4. Isolate failures: exceptions in mail delivery never abort caller transaction.
    """
    recipient = getattr(order.user, "email", "")
    if not recipient:
        return None

    # Idempotency check: avoid duplicate event dispatch
    existing = Notification.objects.filter(order=order, event_type=event_type).first()
    if existing:
        logger.info(
            "Notification %s for order %s already exists (status=%s), skipping duplicate.",
            event_type,
            order.order_number,
            existing.status,
        )
        return existing

    notification = Notification.objects.create(
        order=order,
        recipient=recipient,
        event_type=event_type,
        channel=Notification.CHANNEL_EMAIL,
        status=Notification.STATUS_PENDING,
        metadata=metadata or {},
    )

    subject, body = build_email_content(order, event_type)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@lumera.local")

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=from_email,
            recipient_list=[recipient],
            fail_silently=False,
        )
        notification.status = Notification.STATUS_SENT
        notification.save(update_fields=["status", "updated_at"])
        logger.info("Notification %s successfully sent to %s for order %s", event_type, recipient, order.order_number)
    except Exception as exc:
        logger.error(
            "Notification delivery failed for order %s event %s: %s",
            order.order_number,
            event_type,
            exc,
            exc_info=True,
        )
        notification.status = Notification.STATUS_FAILED
        notification.error_message = str(exc)
        notification.save(update_fields=["status", "error_message", "updated_at"])

    return notification


def safe_dispatch_order_notification(order, event_type: str, metadata: Optional[dict[str, Any]] = None) -> Optional[Notification]:
    """Dispatches notification fail-safely without allowing errors to roll back calling transaction (ADR-0015)."""
    try:
        return send_order_notification(order, event_type, metadata)
    except Exception as exc:
        logger.error("Unexpected error in safe_dispatch_order_notification: %s", exc)
        return None

