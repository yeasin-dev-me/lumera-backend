"""Domain exceptions for Payments (ADR-0014)."""
from rest_framework import exceptions, status
from apps.common.exceptions import ConflictError


class OrderNotPayableError(ConflictError):
    """409 conflict when order cannot be paid (e.g. already paid or cancelled)."""

    default_detail = "This order is not payable."
    default_code = "order_not_payable"


class InvalidPaymentStateTransitionError(ConflictError):
    """409 conflict when an illegal payment state machine transition is attempted."""

    default_detail = "Illegal payment state transition."
    default_code = "invalid_payment_state_transition"


class PaymentVerificationError(exceptions.APIException):
    """400 / 422 error when server-side payment verification fails or amount mismatches."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Payment verification failed."
    default_code = "payment_verification_failed"


class PaymentGatewayError(exceptions.APIException):
    """502 Bad Gateway when external payment provider fails or times out."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Payment gateway communication failure."
    default_code = "payment_gateway_error"
