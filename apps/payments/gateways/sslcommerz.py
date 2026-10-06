"""SSLCommerz Payment Gateway Adapter for Bangladesh (ADR-0014)."""
from decimal import Decimal
import json
import logging
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
from django.conf import settings
from apps.cart.serializers import TWO_PLACES
from apps.payments.exceptions import PaymentGatewayError
from apps.payments.models import Payment
from .base import PaymentGateway

logger = logging.getLogger(__name__)


class SSLCommerzGateway(PaymentGateway):
    """Adapter for SSLCommerz payment gateway in Bangladesh using Python standard library."""

    gateway_id = "sslcommerz"

    def __init__(self):
        self.store_id = getattr(settings, "PAYMENT_SSLCOMMERZ_STORE_ID", "lumera_sandbox")
        self.store_password = getattr(settings, "PAYMENT_SSLCOMMERZ_STORE_PASSWORD", "lumera_secret")
        self.is_sandbox = getattr(settings, "PAYMENT_SSLCOMMERZ_IS_SANDBOX", True)

        if self.is_sandbox:
            self.session_url = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"
            self.validation_url = "https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php"
        else:
            self.session_url = "https://securepay.sslcommerz.com/gwprocess/v4/api.php"
            self.validation_url = "https://securepay.sslcommerz.com/validator/api/validationserverAPI.php"

    def initiate(self, payment: Payment, return_urls: dict[str, str]) -> dict[str, Any]:
        """Initiate hosted session with SSLCommerz."""
        order = payment.order

        payload = {
            "store_id": self.store_id,
            "store_passwd": self.store_password,
            "total_amount": str(payment.amount.quantize(TWO_PLACES)),
            "currency": payment.currency,
            "tran_id": str(payment.public_id),
            "success_url": return_urls.get("success_url", ""),
            "fail_url": return_urls.get("fail_url", ""),
            "cancel_url": return_urls.get("cancel_url", ""),
            "ipn_url": return_urls.get("ipn_url", ""),
            # Customer information
            "cus_name": order.shipping_full_name or "Valued Customer",
            "cus_email": order.user.email,
            "cus_phone": order.shipping_phone or "+8801700000000",
            "cus_add1": order.shipping_address_line1 or "Dhaka",
            "cus_city": order.shipping_city or "Dhaka",
            "cus_country": order.shipping_country or "Bangladesh",
            # Order details
            "shipping_method": "NO",
            "num_of_item": str(max(order.items.count(), 1)),
            "product_name": f"Lumera Order {order.order_number}",
            "product_category": "Skincare",
            "product_profile": "general",
        }

        encoded_data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(
            self.session_url,
            data=encoded_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_text = resp.read().decode("utf-8")
                data = json.loads(raw_text)
        except urllib.error.URLError as exc:
            logger.error("SSLCommerz initiation request failed: %s", exc)
            raise PaymentGatewayError("Failed to communicate with payment gateway.") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            logger.error("SSLCommerz initiation response parsing failed: %s", exc)
            raise PaymentGatewayError("Invalid response from payment gateway.") from exc

        status = data.get("status")
        if status != "SUCCESS":
            error_reason = data.get("failedreason", "Gateway session initiation rejected.")
            logger.warning("SSLCommerz session creation failed: %s", error_reason)
            raise PaymentGatewayError(f"Payment gateway error: {error_reason}")

        redirect_url = data.get("GatewayPageURL") or data.get("redirectGatewayURL", "")
        session_key = data.get("sessionkey", "")

        return {
            "status": "SUCCESS",
            "redirect_url": redirect_url,
            "provider_reference": session_key,
            "raw_response": {
                "status": status,
                "sessionkey": session_key,
                "GatewayPageURL": redirect_url,
            },
        }

    def parse_callback(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """Extract callback values sent by SSLCommerz."""
        return {
            "val_id": request_data.get("val_id", ""),
            "tran_id": request_data.get("tran_id", ""),
            "amount": request_data.get("amount", ""),
            "currency": request_data.get("currency", ""),
            "bank_tran_id": request_data.get("bank_tran_id", ""),
            "card_type": request_data.get("card_type", ""),
            "card_brand": request_data.get("card_brand", ""),
            "status": request_data.get("status", ""),
            "error": request_data.get("error", ""),
        }

    def verify(self, payment: Payment, callback_data: dict[str, Any]) -> dict[str, Any]:
        """Query SSLCommerz Validation Server API server-to-server."""
        val_id = callback_data.get("val_id")
        if not val_id:
            logger.warning("Payment verification missing val_id for payment %s", payment.public_id)
            return {
                "is_valid": False,
                "status": "MISSING_VAL_ID",
                "error": "Missing verification id (val_id).",
            }

        params = {
            "val_id": val_id,
            "store_id": self.store_id,
            "store_passwd": self.store_password,
            "v": 1,
            "format": "json",
        }

        query_str = urllib.parse.urlencode(params)
        url = f"{self.validation_url}?{query_str}"
        req = urllib.request.Request(url, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_text = resp.read().decode("utf-8")
                data = json.loads(raw_text)
        except urllib.error.URLError as exc:
            logger.error("SSLCommerz server-side validation request failed: %s", exc)
            return {
                "is_valid": False,
                "status": "COMMUNICATION_ERROR",
                "error": "Failed to contact gateway verification server.",
            }
        except (ValueError, json.JSONDecodeError) as exc:
            logger.error("SSLCommerz validation response parsing failed: %s", exc)
            return {
                "is_valid": False,
                "status": "INVALID_RESPONSE",
                "error": "Invalid JSON response from gateway verification server.",
            }

        status = data.get("status", "").upper()
        is_valid = status in ("VALID", "VALIDATED")

        try:
            verified_amount = Decimal(str(data.get("amount", "0"))).quantize(TWO_PLACES)
        except Exception:
            verified_amount = Decimal("0.00")

        verified_currency = data.get("currency", "").strip().upper()
        provider_transaction_id = data.get("bank_tran_id") or val_id
        provider_reference = data.get("tran_id") or ""
        card_type = data.get("card_type") or data.get("card_brand", "")

        return {
            "is_valid": is_valid,
            "status": status,
            "verified_amount": verified_amount,
            "verified_currency": verified_currency,
            "provider_transaction_id": provider_transaction_id,
            "provider_reference": provider_reference,
            "card_type": card_type,
            "raw_response": {
                "status": status,
                "tran_id": provider_reference,
                "val_id": val_id,
                "amount": str(verified_amount),
                "currency": verified_currency,
                "bank_tran_id": provider_transaction_id,
                "card_type": card_type,
            },
        }
