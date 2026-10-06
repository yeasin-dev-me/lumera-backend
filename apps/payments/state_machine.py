"""Authoritative payment state machine (ADR-0014)."""
from .exceptions import InvalidPaymentStateTransitionError
from .models import Payment

LEGAL_TRANSITIONS: dict[str, set[str]] = {
    Payment.STATUS_PENDING: {
        Payment.STATUS_INITIATED,
        Payment.STATUS_CANCELLED,
    },
    Payment.STATUS_INITIATED: {
        Payment.STATUS_PROCESSING,
        Payment.STATUS_PAID,
        Payment.STATUS_FAILED,
        Payment.STATUS_CANCELLED,
    },
    Payment.STATUS_PROCESSING: {
        Payment.STATUS_PAID,
        Payment.STATUS_FAILED,
        Payment.STATUS_CANCELLED,
    },
    Payment.STATUS_FAILED: {
        Payment.STATUS_INITIATED,
    },
    Payment.STATUS_CANCELLED: set(),
    Payment.STATUS_PAID: {
        Payment.STATUS_REFUNDED,
    },
    Payment.STATUS_REFUNDED: set(),
}

TERMINAL_STATES = {
    Payment.STATUS_PAID,
    Payment.STATUS_REFUNDED,
}


def can_transition(current_status: str, target_status: str) -> bool:
    """Check if state transition is legal."""
    if current_status == target_status:
        return True
    return target_status in LEGAL_TRANSITIONS.get(current_status, set())


def transition_payment(payment: Payment, target_status: str, save: bool = True) -> Payment:
    """Safely apply a state transition to a Payment instance.
    
    Raises InvalidPaymentStateTransitionError if the transition is illegal.
    """
    if payment.status == target_status:
        return payment

    if not can_transition(payment.status, target_status):
        raise InvalidPaymentStateTransitionError(
            f"Cannot transition payment from '{payment.status}' to '{target_status}'."
        )

    payment.status = target_status
    if save:
        payment.save(update_fields=["status", "updated_at"])
    return payment
