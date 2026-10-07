"""Email provider abstraction and adapters for Lumera (ADR-0018)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from typing import Optional
import uuid
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailDeliveryResult:
    """Standardized delivery result returned by email provider adapters."""
    success: bool
    provider_message_id: str = ""
    error_message: str = ""


class BaseEmailProvider(ABC):
    """Abstract interface defining required provider behaviors."""

    @abstractmethod
    def send(
        self,
        recipient: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
    ) -> EmailDeliveryResult:
        """Dispatches an email message returning delivery status and message id."""
        pass


class DjangoEmailProvider(BaseEmailProvider):
    """Safe email provider utilizing configured Django EMAIL_BACKEND.
    
    Supports locmem (in tests), console (in development), or SMTP/API in production.
    Never lets transport exceptions bubble up unhandled to business operations.
    """

    def send(
        self,
        recipient: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
    ) -> EmailDeliveryResult:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@lumera.local")
        generated_id = f"msg_{uuid.uuid4().hex[:16]}"

        from apps.notifications import services

        try:
            services.send_mail(
                subject=subject,
                message=text_body,
                from_email=from_email,
                recipient_list=[recipient],
                html_message=html_body,
                fail_silently=False,
            )
            logger.info("Email '%s' successfully dispatched to %s via Django backend", subject, recipient)
            return EmailDeliveryResult(
                success=True,
                provider_message_id=generated_id,
            )
        except Exception as exc:
            logger.error("Failed to send email to %s: %s", recipient, exc, exc_info=True)
            return EmailDeliveryResult(
                success=False,
                provider_message_id=generated_id,
                error_message=str(exc),
            )


def get_email_provider() -> BaseEmailProvider:
    """Factory returning configured email provider adapter."""
    return DjangoEmailProvider()
