"""Payment Gateway Registry (ADR-0014)."""
from django.conf import settings
from .base import PaymentGateway
from .sslcommerz import SSLCommerzGateway

_GATEWAYS: dict[str, type[PaymentGateway]] = {
    "sslcommerz": SSLCommerzGateway,
}


def get_gateway(gateway_id: str | None = None) -> PaymentGateway:
    """Retrieve an instantiated PaymentGateway instance by ID."""
    selected_id = gateway_id or getattr(settings, "PAYMENT_DEFAULT_GATEWAY", "sslcommerz")
    normalized = selected_id.lower().strip()

    gateway_cls = _GATEWAYS.get(normalized)
    if not gateway_cls:
        raise ValueError(f"Unsupported payment gateway: '{selected_id}'")

    return gateway_cls()
