"""Transactional notification dispatch services with failure isolation (ADR-0015, ADR-0018)."""
import logging
from typing import Any, Optional
from django.core.mail import send_mail
from django.utils import timezone
from .models import Notification
from .providers import get_email_provider
from .templates import render_template

logger = logging.getLogger(__name__)

__all__ = [
    "send_mail",
    "send_order_notification",
    "dispatch_notification",
    "safe_dispatch_order_notification",
    "safe_dispatch_return_notification",
    "safe_dispatch_refund_notification",
    "safe_dispatch_welcome_notification",
    "resend_notification",
]


def dispatch_notification(
    recipient: str,
    event_type: str,
    context: Optional[dict[str, Any]] = None,
    user: Optional[Any] = None,
    order: Optional[Any] = None,
    return_request: Optional[Any] = None,
    refund: Optional[Any] = None,
    metadata: Optional[dict[str, Any]] = None,
    is_marketing: bool = False,
) -> Optional[Notification]:
    """Dispatches notification with strict failure isolation, idempotency, and consent checking.
    
    1. Marketing consent check (if is_marketing=True): verify customer opted in.
    2. Idempotency check: prevent duplicate notifications for same domain event.
    3. Template rendering: structured, clean text and HTML representation.
    4. Provider dispatch: adapter-based delivery without raising transport exceptions.
    5. Audit persistence: status, timestamps, attempt count, and error capturing.
    """
    if not recipient:
        logger.warning("Attempted to dispatch notification %s without recipient", event_type)
        return None

    ctx = context or {}
    if order and "order" not in ctx:
        ctx["order"] = order
    if user and "user" not in ctx:
        ctx["user"] = user
    if return_request and "return_request" not in ctx:
        ctx["return_request"] = return_request
    if refund and "refund" not in ctx:
        ctx["refund"] = refund

    # 1. Marketing Consent Boundary
    if is_marketing:
        pref = None
        if user:
            pref = getattr(user, "communication_preferences", None)
        if not pref or not pref.marketing_email:
            logger.info("Marketing email suppressed for %s: customer has not opted in.", recipient)
            return None

    # 2. Idempotency Check
    existing = None
    if order:
        existing = Notification.objects.filter(order=order, event_type=event_type).first()
    elif return_request:
        existing = Notification.objects.filter(return_request=return_request, event_type=event_type).first()
    elif refund:
        existing = Notification.objects.filter(refund=refund, event_type=event_type).first()
    elif user and event_type == Notification.EVENT_ACCOUNT_WELCOME:
        existing = Notification.objects.filter(user=user, event_type=Notification.EVENT_ACCOUNT_WELCOME).first()

    if existing:
        logger.info(
            "Notification %s for entity already exists (id=%s, status=%s); suppressing duplicate.",
            event_type,
            existing.public_id,
            existing.status,
        )
        return existing

    # 3. Render content
    try:
        subject, text_body, html_body = render_template(event_type, ctx)
    except Exception as exc:
        logger.error("Template rendering failed for event %s: %s", event_type, exc, exc_info=True)
        subject = f"Notification: {event_type}"
        text_body = "There is an update regarding your Lumera account."
        html_body = None

    # 4. Create Notification record in pending state
    notification = Notification.objects.create(
        user=user,
        order=order,
        return_request=return_request,
        refund=refund,
        recipient=recipient,
        subject=subject,
        event_type=event_type,
        channel=Notification.CHANNEL_EMAIL,
        status=Notification.STATUS_PENDING,
        attempt_count=1,
        metadata=metadata or {},
    )

    # 5. Dispatch via Provider
    provider = get_email_provider()
    result = provider.send(
        recipient=recipient,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

    now = timezone.now()
    if result.success:
        notification.status = Notification.STATUS_SENT
        notification.sent_at = now
        notification.provider_message_id = result.provider_message_id
        notification.error_message = ""
        notification.save(update_fields=["status", "sent_at", "provider_message_id", "error_message", "updated_at"])
        logger.info("Notification %s successfully sent to %s (id=%s)", event_type, recipient, notification.public_id)
    else:
        notification.status = Notification.STATUS_FAILED
        notification.failed_at = now
        notification.provider_message_id = result.provider_message_id
        notification.error_message = result.error_message
        notification.save(update_fields=["status", "failed_at", "provider_message_id", "error_message", "updated_at"])
        logger.warning("Notification %s delivery failed for %s: %s", event_type, recipient, result.error_message)

    return notification


def safe_dispatch_order_notification(
    order: Any,
    event_type: str,
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[Notification]:
    """Fail-safe order lifecycle notification dispatch (backward compatible with Step 8)."""
    try:
        user = getattr(order, "user", None)
        recipient = getattr(user, "email", "") or getattr(order, "shipping_email", "")
        if not recipient:
            return None
        return dispatch_notification(
            recipient=recipient,
            event_type=event_type,
            user=user,
            order=order,
            metadata=metadata,
        )
    except Exception as exc:
        logger.error("Unexpected error in safe_dispatch_order_notification: %s", exc)
        return None


def safe_dispatch_return_notification(
    return_request: Any,
    event_type: str,
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[Notification]:
    """Fail-safe return request notification dispatch."""
    try:
        user = getattr(return_request, "user", None)
        recipient = getattr(user, "email", "")
        if not recipient:
            return None
        return dispatch_notification(
            recipient=recipient,
            event_type=event_type,
            user=user,
            order=getattr(return_request, "order", None),
            return_request=return_request,
            metadata=metadata,
        )
    except Exception as exc:
        logger.error("Unexpected error in safe_dispatch_return_notification: %s", exc)
        return None


def safe_dispatch_refund_notification(
    refund: Any,
    event_type: str,
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[Notification]:
    """Fail-safe refund notification dispatch."""
    try:
        order = getattr(refund, "order", None)
        user = getattr(order, "user", None)
        recipient = getattr(user, "email", "")
        if not recipient:
            return None
        return dispatch_notification(
            recipient=recipient,
            event_type=event_type,
            user=user,
            order=order,
            refund=refund,
            metadata=metadata,
        )
    except Exception as exc:
        logger.error("Unexpected error in safe_dispatch_refund_notification: %s", exc)
        return None


def safe_dispatch_welcome_notification(
    user: Any,
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[Notification]:
    """Fail-safe customer account registration welcome notification."""
    try:
        recipient = getattr(user, "email", "")
        if not recipient:
            return None
        return dispatch_notification(
            recipient=recipient,
            event_type=Notification.EVENT_ACCOUNT_WELCOME,
            user=user,
            metadata=metadata,
        )
    except Exception as exc:
        logger.error("Unexpected error in safe_dispatch_welcome_notification: %s", exc)
        return None


def resend_notification(notification: Notification) -> Notification:
    """Manually and idempotently resend/retry a notification with attempt auditing."""
    notification.attempt_count += 1
    notification.status = Notification.STATUS_PENDING
    notification.save(update_fields=["attempt_count", "status", "updated_at"])

    ctx = {
        "order": notification.order,
        "user": notification.user,
        "return_request": notification.return_request,
        "refund": notification.refund,
    }

    try:
        subject, text_body, html_body = render_template(notification.event_type, ctx)
    except Exception as exc:
        logger.error("Template rendering failed on resend: %s", exc)
        subject = notification.subject or f"Notification: {notification.event_type}"
        text_body = "There is an update regarding your Lumera account."
        html_body = None

    provider = get_email_provider()
    result = provider.send(
        recipient=notification.recipient,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

    now = timezone.now()
    if result.success:
        notification.status = Notification.STATUS_SENT
        notification.sent_at = now
        notification.provider_message_id = result.provider_message_id
        notification.error_message = ""
        notification.save(update_fields=["status", "sent_at", "provider_message_id", "error_message", "updated_at"])
    else:
        notification.status = Notification.STATUS_FAILED
        notification.failed_at = now
        notification.provider_message_id = result.provider_message_id
        notification.error_message = result.error_message
        notification.save(update_fields=["status", "failed_at", "provider_message_id", "error_message", "updated_at"])

    return notification


# Alias for backward compatibility with Step 8 callers and tests
send_order_notification = safe_dispatch_order_notification
