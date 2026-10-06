"""Payment Gateway Interface and Base Class (ADR-0014)."""
from abc import ABC, abstractmethod
from typing import Any
from apps.payments.models import Payment


class PaymentGateway(ABC):
    """Abstract payment gateway adapter interface."""

    gateway_id: str

    @abstractmethod
    def initiate(self, payment: Payment, return_urls: dict[str, str]) -> dict[str, Any]:
        """Initiate payment session with provider.
        
        Returns dict containing redirect_url, provider_reference, and raw_response.
        """
        pass

    @abstractmethod
    def parse_callback(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """Extract and normalize fields from incoming gateway callback / webhook."""
        pass

    @abstractmethod
    def verify(self, payment: Payment, callback_data: dict[str, Any]) -> dict[str, Any]:
        """Perform server-to-server authoritative transaction validation with gateway.
        
        Returns dict with is_valid, verified_amount, verified_currency, provider_transaction_id.
        """
        pass
