"""Authoritative business services for Payments (ADR-0014, BR-01, BR-03, BR-12)."""
import logging
from typing import Any
import uuid
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions
from apps.orders.models import Order, OrderStatusHistory
from .exceptions import OrderNotPayableError
from .gateways import get_gateway
from .models import Payment, PaymentAttempt
from .state_machine import transition_payment

logger = logging.getLogger(__name__)


def initiate_payment(
    user,
    order_public_id: str | uuid.UUID,
    gateway_id: str | None = None,
    return_url: str | None = None,
) -> tuple[Payment, dict[str, Any]]:
    """Initiate a payment attempt for a payable order (ADR-0014).
    
    1. Authenticates order ownership (Customer isolation).
    2. Validates order is payable (not already paid, not cancelled).
    3. Locks order row.
    4. Authoritatively derives amount from order.total.
    5. Dispatches session creation to configured payment gateway.
    6. Records PaymentAttempt and transitions payment status to 'initiated'.
    """
    gateway = get_gateway(gateway_id)

    with transaction.atomic():
        try:
            val_uuid = uuid.UUID(str(order_public_id))
        except (ValueError, TypeError):
            raise exceptions.NotFound("Order not found.")

        # Customer isolation: Must belong to authenticated user
        order = (
            Order.objects.select_for_update()
            .filter(public_id=val_uuid, user=user)
            .first()
        )
        if not order:
            raise exceptions.NotFound("Order not found.")

        # Payable order rules
        if order.payment_status == Order.PAYMENT_PAID:
            raise OrderNotPayableError("This order has already been paid.")

        if order.status == Order.STATUS_CANCELLED:
            raise OrderNotPayableError("Cancelled orders cannot be paid.")

        # Create or retrieve Payment record
        payment = Payment.objects.filter(order=order).first()
        if payment and payment.status == Payment.STATUS_PAID:
            raise OrderNotPayableError("This order has already been paid.")

        if not payment:
            payment = Payment.objects.create(
                order=order,
                gateway=gateway.gateway_id,
                amount=order.total,
                currency=order.currency,
                status=Payment.STATUS_PENDING,
            )
        else:
            payment.gateway = gateway.gateway_id
            payment.amount = order.total
            payment.currency = order.currency
            payment.save(update_fields=["gateway", "amount", "currency", "updated_at"])

        attempt_count = PaymentAttempt.objects.filter(payment=payment).count() + 1

        callback_base = getattr(settings, "PAYMENT_CALLBACK_BASE_URL", "http://localhost:8000").rstrip("/")
        return_urls = {
            "ipn_url": f"{callback_base}/api/v1/internal/payments/webhook/{gateway.gateway_id}/",
            "success_url": return_url or f"{callback_base}/checkout/confirmation/{order.public_id}?payment=success",
            "fail_url": return_url or f"{callback_base}/checkout/confirmation/{order.public_id}?payment=fail",
            "cancel_url": return_url or f"{callback_base}/checkout/confirmation/{order.public_id}?payment=cancel",
        }

        try:
            init_res = gateway.initiate(payment, return_urls)
        except Exception as exc:
            PaymentAttempt.objects.create(
                payment=payment,
                order=order,
                attempt_number=attempt_count,
                gateway=gateway.gateway_id,
                amount=payment.amount,
                currency=payment.currency,
                status=PaymentAttempt.STATUS_FAILED,
                error_message=str(exc),
            )
            transition_payment(payment, Payment.STATUS_FAILED)
            raise

        payment.provider_reference = init_res.get("provider_reference", "")
        transition_payment(payment, Payment.STATUS_INITIATED, save=False)
        payment.save(update_fields=["status", "provider_reference", "updated_at"])

        PaymentAttempt.objects.create(
            payment=payment,
            order=order,
            attempt_number=attempt_count,
            gateway=gateway.gateway_id,
            provider_reference=payment.provider_reference,
            amount=payment.amount,
            currency=payment.currency,
            status=PaymentAttempt.STATUS_INITIATED,
            raw_response=init_res.get("raw_response", {}),
        )

        return payment, init_res


def process_gateway_callback(gateway_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Process incoming payment webhook / IPN callback idempotently (ADR-0014).
    
    1. Parse callback payload.
    2. Row-lock referenced Payment and Order.
    3. Enforce idempotency: if already paid, return status='already_paid'.
    4. Call gateway server-to-server transaction verification API.
    5. Authoritatively verify amount and currency against order.total.
    6. Transition payment status to 'paid' and order.payment_status to 'paid'.
    """
    gateway = get_gateway(gateway_id)
    parsed = gateway.parse_callback(payload)

    tran_id = parsed.get("tran_id") or ""
    val_id = parsed.get("val_id") or ""

    if not tran_id and not val_id:
        return {
            "status": "rejected",
            "message": "Missing transaction identification in callback.",
        }

    with transaction.atomic():
        payment = None
        # Try tran_id as UUID
        try:
            payment = Payment.objects.select_for_update().filter(public_id=uuid.UUID(str(tran_id))).first()
        except (ValueError, TypeError):
            pass

        if not payment and tran_id:
            payment = Payment.objects.select_for_update().filter(provider_reference=tran_id).first()

        if not payment and val_id:
            payment = Payment.objects.select_for_update().filter(provider_reference=val_id).first()

        if not payment and tran_id:
            try:
                order_match = Order.objects.filter(public_id=uuid.UUID(str(tran_id))).first()
                if order_match:
                    payment = Payment.objects.select_for_update().filter(order=order_match).first()
            except (ValueError, TypeError):
                pass

        if not payment:
            logger.warning("Payment not found for callback tran_id=%s, val_id=%s", tran_id, val_id)
            return {
                "status": "rejected",
                "message": f"Payment not found for transaction reference: {tran_id or val_id}",
            }

        order = Order.objects.select_for_update().get(pk=payment.order_id)

        # Idempotency check: Repeated webhook callbacks return 200 without duplicate updates
        if payment.status == Payment.STATUS_PAID and order.payment_status == Order.PAYMENT_PAID:
            logger.info("Payment %s for Order %s is already paid (idempotent callback)", payment.public_id, order.order_number)
            return {
                "status": "already_paid",
                "message": "Payment has already been authoritatively verified and marked as paid.",
                "payment_public_id": str(payment.public_id),
                "order_number": order.order_number,
            }

        # Query gateway verification server-to-server
        verification = gateway.verify(payment, parsed)
        attempt_num = PaymentAttempt.objects.filter(payment=payment).count() + 1

        if not verification.get("is_valid"):
            err_msg = verification.get("error", "Gateway verification failed or was rejected.")
            logger.warning("Gateway verification rejected for payment %s: %s", payment.public_id, err_msg)
            transition_payment(payment, Payment.STATUS_FAILED)
            PaymentAttempt.objects.create(
                payment=payment,
                order=order,
                attempt_number=attempt_num,
                gateway=gateway_id,
                provider_reference=parsed.get("tran_id", ""),
                provider_transaction_id=parsed.get("bank_tran_id", ""),
                amount=payment.amount,
                currency=payment.currency,
                status=PaymentAttempt.STATUS_FAILED,
                error_message=err_msg,
                raw_response=verification.get("raw_response", {}),
            )
            return {
                "status": "failed",
                "message": err_msg,
                "payment_public_id": str(payment.public_id),
                "order_number": order.order_number,
            }

        # Authoritative Money & Currency Check (Defense in Depth)
        verified_amount = verification.get("verified_amount")
        verified_currency = verification.get("verified_currency")

        if verified_amount != payment.amount or verified_amount != order.total:
            err_msg = (
                f"Amount mismatch. Authoritative order total is {order.total}, "
                f"gateway reported {verified_amount}."
            )
            logger.error("Security alert: Payment %s amount tampering detected: %s", payment.public_id, err_msg)
            transition_payment(payment, Payment.STATUS_FAILED)
            PaymentAttempt.objects.create(
                payment=payment,
                order=order,
                attempt_number=attempt_num,
                gateway=gateway_id,
                provider_reference=parsed.get("tran_id", ""),
                provider_transaction_id=verification.get("provider_transaction_id", ""),
                amount=verified_amount or payment.amount,
                currency=payment.currency,
                status=PaymentAttempt.STATUS_FAILED,
                error_message=err_msg,
                raw_response=verification.get("raw_response", {}),
            )
            return {
                "status": "rejected",
                "message": err_msg,
                "payment_public_id": str(payment.public_id),
                "order_number": order.order_number,
            }

        if verified_currency and verified_currency.upper() != payment.currency.upper():
            err_msg = (
                f"Currency mismatch. Expected {payment.currency}, got {verified_currency}."
            )
            logger.error("Security alert: Payment %s currency mismatch: %s", payment.public_id, err_msg)
            transition_payment(payment, Payment.STATUS_FAILED)
            return {
                "status": "rejected",
                "message": err_msg,
                "payment_public_id": str(payment.public_id),
                "order_number": order.order_number,
            }

        # Authoritative success transition
        now = timezone.now()
        payment.provider_transaction_id = verification.get("provider_transaction_id", "")
        payment.method = verification.get("card_type", "")
        payment.paid_at = now
        payment.metadata = verification.get("raw_response", {})
        transition_payment(payment, Payment.STATUS_PAID, save=False)
        payment.save(
            update_fields=[
                "status",
                "provider_transaction_id",
                "method",
                "paid_at",
                "metadata",
                "updated_at",
            ]
        )

        order.payment_status = Order.PAYMENT_PAID
        if order.status == Order.STATUS_PENDING:
            order.status = Order.STATUS_CONFIRMED
        order.save(update_fields=["payment_status", "status", "updated_at"])

        OrderStatusHistory.objects.create(
            order=order,
            from_status=Order.STATUS_PENDING,
            to_status=Order.STATUS_CONFIRMED,
            changed_by=None,
            reason=f"Payment verified via {gateway_id.upper()} (Txn: {payment.provider_transaction_id})",
        )

        PaymentAttempt.objects.create(
            payment=payment,
            order=order,
            attempt_number=attempt_num,
            gateway=gateway_id,
            provider_reference=parsed.get("tran_id", ""),
            provider_transaction_id=payment.provider_transaction_id,
            amount=payment.amount,
            currency=payment.currency,
            status=PaymentAttempt.STATUS_SUCCESSFUL,
            error_message="",
            raw_response=verification.get("raw_response", {}),
        )

        logger.info(
            "Payment %s authoritatively verified and marked as paid for Order %s (Txn: %s)",
            payment.public_id,
            order.order_number,
            payment.provider_transaction_id,
        )

        return {
            "status": "paid",
            "message": "Payment verified and recorded successfully.",
            "payment_public_id": str(payment.public_id),
            "order_number": order.order_number,
        }
