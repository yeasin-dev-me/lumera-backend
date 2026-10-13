"""Comprehensive unit, service, and API tests for Payment domain (ADR-0014, Step 7)."""
from decimal import Decimal
import json
import unittest.mock as mock
from django.db import IntegrityError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from apps.orders.models import Order
from apps.payments.exceptions import InvalidPaymentStateTransitionError, OrderNotPayableError
from apps.payments.gateways import get_gateway
from apps.payments.gateways.sslcommerz import SSLCommerzGateway
from apps.payments.models import Payment, PaymentAttempt
from apps.payments.services import initiate_payment, process_gateway_callback
from apps.payments.state_machine import can_transition, transition_payment
from apps.users.models import User


class PaymentModelAndStateMachineTests(TestCase):
    """Test Payment model, constraints, and authoritative state machine transitions."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="payer@example.com",
            password="StrongPassword2026!",
        )
        self.order = Order.objects.create(
            order_number="LUM-20261006-PAY001",
            user=self.user,
            status=Order.STATUS_PENDING,
            payment_status=Order.PAYMENT_PENDING,
            subtotal=Decimal("84.00"),
            shipping_cost=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("84.00"),
            shipping_full_name="Jane Payer",
            shipping_phone="+8801700000000",
            shipping_address_line1="Gulshan 2",
            shipping_city="Dhaka",
        )

    def test_payment_creation_and_defaults(self):
        payment = Payment.objects.create(
            order=self.order,
            gateway="sslcommerz",
            amount=self.order.total,
            currency="USD",
        )
        self.assertEqual(payment.status, Payment.STATUS_PENDING)
        self.assertEqual(payment.amount, Decimal("84.00"))
        self.assertIsNotNone(payment.public_id)

    def test_amount_must_be_positive_constraint(self):
        with self.assertRaises(IntegrityError):
            Payment.objects.create(
                order=self.order,
                gateway="sslcommerz",
                amount=Decimal("0.00"),
                currency="USD",
            )

    def test_unique_paid_payment_per_order_constraint(self):
        Payment.objects.create(
            order=self.order,
            gateway="sslcommerz",
            amount=Decimal("84.00"),
            currency="USD",
            status=Payment.STATUS_PAID,
        )
        with self.assertRaises(IntegrityError):
            Payment.objects.create(
                order=self.order,
                gateway="sslcommerz",
                amount=Decimal("84.00"),
                currency="USD",
                status=Payment.STATUS_PAID,
            )

    def test_legal_state_machine_transitions(self):
        payment = Payment.objects.create(
            order=self.order,
            gateway="sslcommerz",
            amount=Decimal("84.00"),
            currency="USD",
            status=Payment.STATUS_PENDING,
        )
        self.assertTrue(can_transition(payment.status, Payment.STATUS_INITIATED))
        transition_payment(payment, Payment.STATUS_INITIATED)
        self.assertEqual(payment.status, Payment.STATUS_INITIATED)

        self.assertTrue(can_transition(payment.status, Payment.STATUS_PROCESSING))
        transition_payment(payment, Payment.STATUS_PROCESSING)
        self.assertEqual(payment.status, Payment.STATUS_PROCESSING)

        self.assertTrue(can_transition(payment.status, Payment.STATUS_PAID))
        transition_payment(payment, Payment.STATUS_PAID)
        self.assertEqual(payment.status, Payment.STATUS_PAID)

    def test_illegal_state_machine_transitions_rejected(self):
        payment = Payment.objects.create(
            order=self.order,
            gateway="sslcommerz",
            amount=Decimal("84.00"),
            currency="USD",
            status=Payment.STATUS_PAID,
        )
        # Terminal state: Cannot transition back to pending or failed
        self.assertFalse(can_transition(payment.status, Payment.STATUS_PENDING))
        with self.assertRaises(InvalidPaymentStateTransitionError):
            transition_payment(payment, Payment.STATUS_PENDING)

        self.assertFalse(can_transition(payment.status, Payment.STATUS_FAILED))
        with self.assertRaises(InvalidPaymentStateTransitionError):
            transition_payment(payment, Payment.STATUS_FAILED)


class SSLCommerzGatewayAdapterTests(TestCase):
    """Test SSLCommerz gateway initiate, callback parse, and server-side verification."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="gw@example.com",
            password="StrongPassword2026!",
        )
        self.order = Order.objects.create(
            order_number="LUM-20261006-PAY002",
            user=self.user,
            status=Order.STATUS_PENDING,
            payment_status=Order.PAYMENT_PENDING,
            subtotal=Decimal("50.00"),
            shipping_cost=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("50.00"),
            shipping_full_name="Gateway Tester",
            shipping_phone="+8801711111111",
            shipping_address_line1="Banani",
            shipping_city="Dhaka",
        )
        self.payment = Payment.objects.create(
            order=self.order,
            gateway="sslcommerz",
            amount=Decimal("50.00"),
            currency="USD",
        )
        self.gateway = get_gateway("sslcommerz")
        self.assertIsInstance(self.gateway, SSLCommerzGateway)

    @mock.patch("urllib.request.urlopen")
    def test_initiate_session_success(self, mock_urlopen):
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "status": "SUCCESS",
                "sessionkey": "TEST_SESSION_KEY_12345",
                "GatewayPageURL": "https://sandbox.sslcommerz.com/EasyCheckOut/test12345",
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = self.gateway.initiate(
            self.payment,
            return_urls={"ipn_url": "http://localhost/ipn", "success_url": "http://localhost/success"},
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["provider_reference"], "TEST_SESSION_KEY_12345")
        self.assertEqual(res["redirect_url"], "https://sandbox.sslcommerz.com/EasyCheckOut/test12345")

    def test_parse_callback(self):
        raw_payload = {
            "val_id": "VAL_123",
            "tran_id": str(self.payment.public_id),
            "amount": "50.00",
            "currency": "USD",
            "bank_tran_id": "BANK_TXN_999",
            "card_type": "VISA-BRAC",
            "status": "VALID",
        }
        parsed = self.gateway.parse_callback(raw_payload)
        self.assertEqual(parsed["val_id"], "VAL_123")
        self.assertEqual(parsed["tran_id"], str(self.payment.public_id))
        self.assertEqual(parsed["bank_tran_id"], "BANK_TXN_999")

    @mock.patch("urllib.request.urlopen")
    def test_verify_server_side_success(self, mock_urlopen):
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "status": "VALID",
                "tran_id": str(self.payment.public_id),
                "val_id": "VAL_123",
                "amount": "50.00",
                "currency": "USD",
                "bank_tran_id": "BANK_TXN_999",
                "card_type": "VISA",
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        verification = self.gateway.verify(self.payment, {"val_id": "VAL_123"})
        self.assertTrue(verification["is_valid"])
        self.assertEqual(verification["verified_amount"], Decimal("50.00"))
        self.assertEqual(verification["verified_currency"], "USD")
        self.assertEqual(verification["provider_transaction_id"], "BANK_TXN_999")


class PaymentServiceAndSecurityTests(TestCase):
    """Test payment business services, customer isolation, tampering rejection, and idempotency."""

    def setUp(self):
        self.user1 = User.objects.create_user(email="user1@example.com", password="StrongPassword2026!")
        self.user2 = User.objects.create_user(email="user2@example.com", password="StrongPassword2026!")

        self.order1 = Order.objects.create(
            order_number="LUM-20261006-ORD001",
            user=self.user1,
            status=Order.STATUS_PENDING,
            payment_status=Order.PAYMENT_PENDING,
            subtotal=Decimal("100.00"),
            shipping_cost=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("100.00"),
            shipping_full_name="User One",
            shipping_phone="+8801700000001",
            shipping_address_line1="Road 1",
            shipping_city="Dhaka",
        )

    @mock.patch("urllib.request.urlopen")
    def test_initiate_payment_authoritative_amount(self, mock_urlopen):
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "status": "SUCCESS",
                "sessionkey": "SESSION_ABC",
                "GatewayPageURL": "https://sandbox.sslcommerz.com/pay/abc",
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        payment, init_res = initiate_payment(
            user=self.user1,
            order_public_id=self.order1.public_id,
            gateway_id="sslcommerz",
        )
        self.assertEqual(payment.amount, Decimal("100.00"))
        self.assertEqual(payment.status, Payment.STATUS_INITIATED)
        self.assertEqual(init_res["redirect_url"], "https://sandbox.sslcommerz.com/pay/abc")

        # Verify PaymentAttempt record created
        attempt = PaymentAttempt.objects.filter(payment=payment).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.amount, Decimal("100.00"))

    def test_customer_isolation_cannot_initiate_another_users_order(self):
        with self.assertRaises(Exception):
            initiate_payment(
                user=self.user2,
                order_public_id=self.order1.public_id,
            )

    def test_paid_order_cannot_be_initiated_again(self):
        self.order1.payment_status = Order.PAYMENT_PAID
        self.order1.save()

        with self.assertRaises(OrderNotPayableError):
            initiate_payment(
                user=self.user1,
                order_public_id=self.order1.public_id,
            )

    def test_cancelled_order_cannot_be_initiated(self):
        self.order1.status = Order.STATUS_CANCELLED
        self.order1.save()

        with self.assertRaises(OrderNotPayableError):
            initiate_payment(
                user=self.user1,
                order_public_id=self.order1.public_id,
            )

    @mock.patch("urllib.request.urlopen")
    def test_successful_callback_marks_payment_and_order_paid(self, mock_urlopen):
        payment = Payment.objects.create(
            order=self.order1,
            gateway="sslcommerz",
            amount=Decimal("100.00"),
            currency="USD",
            status=Payment.STATUS_INITIATED,
        )

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "status": "VALID",
                "tran_id": str(payment.public_id),
                "val_id": "VALID_VAL_1",
                "amount": "100.00",
                "currency": "USD",
                "bank_tran_id": "BANK_TXN_SUCCESS",
                "card_type": "BKASH",
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        callback_payload = {
            "tran_id": str(payment.public_id),
            "val_id": "VALID_VAL_1",
            "amount": "100.00",
            "currency": "USD",
        }

        result = process_gateway_callback("sslcommerz", callback_payload)
        self.assertEqual(result["status"], "paid")

        payment.refresh_from_db()
        self.order1.refresh_from_db()

        self.assertEqual(payment.status, Payment.STATUS_PAID)
        self.assertEqual(self.order1.payment_status, Order.PAYMENT_PAID)
        self.assertEqual(self.order1.status, Order.STATUS_CONFIRMED)
        self.assertEqual(payment.provider_transaction_id, "BANK_TXN_SUCCESS")
        self.assertIsNotNone(payment.paid_at)

    @mock.patch("urllib.request.urlopen")
    def test_callback_idempotency_duplicate_calls_safe(self, mock_urlopen):
        payment = Payment.objects.create(
            order=self.order1,
            gateway="sslcommerz",
            amount=Decimal("100.00"),
            currency="USD",
            status=Payment.STATUS_INITIATED,
        )

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "status": "VALID",
                "tran_id": str(payment.public_id),
                "val_id": "VALID_VAL_IDEMP",
                "amount": "100.00",
                "currency": "USD",
                "bank_tran_id": "BANK_IDEMP",
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        payload = {"tran_id": str(payment.public_id), "val_id": "VALID_VAL_IDEMP"}

        # First callback -> paid
        res1 = process_gateway_callback("sslcommerz", payload)
        self.assertEqual(res1["status"], "paid")

        # Second callback -> idempotent already_paid
        res2 = process_gateway_callback("sslcommerz", payload)
        self.assertEqual(res2["status"], "already_paid")

        # Third callback -> idempotent already_paid
        res3 = process_gateway_callback("sslcommerz", payload)
        self.assertEqual(res3["status"], "already_paid")

        # No duplicate payments created
        self.assertEqual(Payment.objects.filter(order=self.order1).count(), 1)

    @mock.patch("urllib.request.urlopen")
    def test_amount_tampering_rejected_and_order_remains_unpaid(self, mock_urlopen):
        payment = Payment.objects.create(
            order=self.order1,
            gateway="sslcommerz",
            amount=Decimal("100.00"),
            currency="USD",
            status=Payment.STATUS_INITIATED,
        )

        # Attacker tampered: paid only 1.00 for a 100.00 order
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "status": "VALID",
                "tran_id": str(payment.public_id),
                "val_id": "VAL_TAMPER",
                "amount": "1.00",
                "currency": "USD",
                "bank_tran_id": "BANK_TAMPER",
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        payload = {"tran_id": str(payment.public_id), "val_id": "VAL_TAMPER"}
        res = process_gateway_callback("sslcommerz", payload)
        self.assertEqual(res["status"], "rejected")

        payment.refresh_from_db()
        self.order1.refresh_from_db()

        self.assertEqual(payment.status, Payment.STATUS_FAILED)
        self.assertEqual(self.order1.payment_status, Order.PAYMENT_PENDING)


class PaymentAPITests(TestCase):
    """Test customer payment endpoints and webhook API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="api_payer@example.com", password="StrongPassword2026!")
        self.other_user = User.objects.create_user(email="other_payer@example.com", password="StrongPassword2026!")

        self.order = Order.objects.create(
            order_number="LUM-20261006-API001",
            user=self.user,
            status=Order.STATUS_PENDING,
            payment_status=Order.PAYMENT_PENDING,
            subtotal=Decimal("75.00"),
            shipping_cost=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("75.00"),
            shipping_full_name="API Tester",
            shipping_phone="+8801722222222",
            shipping_address_line1="Dhanmondi",
            shipping_city="Dhaka",
        )

    def test_unauthenticated_initiation_rejected(self):
        url = f"/api/v1/customer/orders/{self.order.public_id}/payment/"
        res = self.client.post(url, {})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @mock.patch("urllib.request.urlopen")
    def test_authenticated_customer_initiation_success(self, mock_urlopen):
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "status": "SUCCESS",
                "sessionkey": "SES_KEY_API",
                "GatewayPageURL": "https://sandbox.sslcommerz.com/checkout/123",
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/customer/orders/{self.order.public_id}/payment/"
        res = self.client.post(url, {"gateway": "sslcommerz"})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()
        self.assertEqual(data["amount"], "75.00")
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["status"], "initiated")
        self.assertEqual(data["redirect_url"], "https://sandbox.sslcommerz.com/checkout/123")

    def test_cross_customer_initiation_rejected(self):
        self.client.force_authenticate(user=self.other_user)
        url = f"/api/v1/customer/orders/{self.order.public_id}/payment/"
        res = self.client.post(url, {})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_payment_status_query(self):
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/customer/orders/{self.order.public_id}/payment/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data["order_number"], self.order.order_number)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["amount"], "75.00")

    @mock.patch("urllib.request.urlopen")
    def test_webhook_endpoint_intake(self, mock_urlopen):
        payment = Payment.objects.create(
            order=self.order,
            gateway="sslcommerz",
            amount=Decimal("75.00"),
            currency="USD",
            status=Payment.STATUS_INITIATED,
        )

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "status": "VALID",
                "tran_id": str(payment.public_id),
                "val_id": "VAL_HOOK",
                "amount": "75.00",
                "currency": "USD",
                "bank_tran_id": "BANK_HOOK_1",
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        webhook_url = "/api/v1/internal/payments/webhook/sslcommerz/"
        payload = {
            "tran_id": str(payment.public_id),
            "val_id": "VAL_HOOK",
        }
        res = self.client.post(webhook_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data["status"], "paid")

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PAYMENT_PAID)
