"""Tests for Step 11: Customer Communication & Engagement (ADR-0018, BR-31)."""
from decimal import Decimal
from unittest.mock import patch
import pytest
from django.core import mail
from apps.users.models import User, Role
from apps.categories.models import Category
from apps.products.models import Product
from apps.orders.models import Order
from apps.notifications.models import Notification, CommunicationPreference
from apps.notifications.services import (
    dispatch_notification,
    safe_dispatch_order_notification,
)


@pytest.fixture
def test_user(db):
    user = User.objects.create_user(
        email="customer11@example.com",
        password="Password123!",
        first_name="Customer",
        last_name="Eleven",
    )
    CommunicationPreference.objects.get_or_create(user=user)
    return user


@pytest.fixture
def other_user(db):
    user = User.objects.create_user(
        email="other11@example.com",
        password="Password123!",
        first_name="Other",
        last_name="Person",
    )
    CommunicationPreference.objects.get_or_create(user=user)
    return user


@pytest.fixture
def staff_user(db):
    role, _ = Role.objects.get_or_create(
        name="notification_admin",
        defaults={"permissions": ["notifications.read", "notifications.manage"]},
    )
    user = User.objects.create_user(
        email="staff11@example.com",
        password="Password123!",
        first_name="Staff",
        last_name="Admin",
        is_staff=True,
    )
    user.roles.add(role)
    return user


@pytest.fixture
def test_order(db, test_user):
    cat = Category.objects.create(name="Botanicals", slug="botanicals-11", status="active")
    Product.objects.create(
        name="Elixir 11",
        slug="elixir-11",
        sku="SKU-11",
        category=cat,
        price=Decimal("50.00"),
        stock_quantity=10,
        status="active",
    )
    order = Order.objects.create(
        order_number="ORD-11001",
        user=test_user,
        status=Order.STATUS_PENDING,
        subtotal=Decimal("50.00"),
        total=Decimal("50.00"),
        shipping_full_name="Customer Eleven",
        shipping_phone="123456",
        shipping_address_line1="11 Botanical Way",
        shipping_city="City",
    )
    return order


@pytest.mark.django_db
class TestNotificationDispatch:
    """Verifies event dispatch, idempotency, failure isolation, and template rendering."""

    def test_order_placed_notification_dispatched(self, test_order):
        mail.outbox = []
        notif = safe_dispatch_order_notification(test_order, Notification.EVENT_ORDER_PLACED)

        assert notif is not None
        assert notif.status == Notification.STATUS_SENT
        assert notif.event_type == Notification.EVENT_ORDER_PLACED
        assert notif.recipient == test_order.user.email
        assert "Order Confirmation" in notif.subject
        assert notif.sent_at is not None
        assert len(mail.outbox) == 1
        assert "ORD-11001" in mail.outbox[0].subject

    def test_duplicate_event_is_suppressed(self, test_order):
        notif1 = safe_dispatch_order_notification(test_order, Notification.EVENT_ORDER_PLACED)
        mail.outbox = []

        notif2 = safe_dispatch_order_notification(test_order, Notification.EVENT_ORDER_PLACED)
        assert notif1.id == notif2.id
        assert len(mail.outbox) == 0  # No duplicate email sent

    def test_failure_isolation_preserves_error_record(self, test_order):
        with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=Exception("SMTP Connection Refused")):
            notif = safe_dispatch_order_notification(test_order, Notification.EVENT_ORDER_SHIPPED)

        assert notif is not None
        assert notif.status == Notification.STATUS_FAILED
        assert "SMTP Connection Refused" in notif.error_message
        assert notif.failed_at is not None

    def test_marketing_preference_boundary(self, test_user):
        pref = test_user.communication_preferences
        pref.marketing_email = False
        pref.save()

        # Marketing notification should be suppressed when opt-in is false
        notif_mkt = dispatch_notification(
            recipient=test_user.email,
            event_type="promotional_newsletter",
            user=test_user,
            is_marketing=True,
        )
        assert notif_mkt is None

        # Transactional notification MUST NOT be suppressed even when marketing is false
        notif_tx = dispatch_notification(
            recipient=test_user.email,
            event_type=Notification.EVENT_ACCOUNT_WELCOME,
            user=test_user,
            is_marketing=False,
        )
        assert notif_tx is not None
        assert notif_tx.status == Notification.STATUS_SENT


@pytest.mark.django_db
class TestCustomerCommunicationAPI:
    """Verifies customer-facing preference and notification endpoints."""

    def test_customer_can_read_and_update_preferences(self, client, test_user):
        from rest_framework_simplejwt.tokens import RefreshToken

        token = str(RefreshToken.for_user(test_user).access_token)
        client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        # GET preferences
        res_get = client.get("/api/v1/customer/communication-preferences/")
        assert res_get.status_code == 200
        assert res_get.json()["marketing_email"] is False
        assert res_get.json()["order_updates_email"] is True

        # PATCH preferences
        res_patch = client.patch(
            "/api/v1/customer/communication-preferences/",
            data={"marketing_email": True, "marketing_sms": True},
            content_type="application/json",
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["marketing_email"] is True
        assert res_patch.json()["marketing_sms"] is True

    def test_customer_notification_history_isolation(self, client, test_user, other_user, test_order):
        from rest_framework_simplejwt.tokens import RefreshToken

        # Create notification for test_user
        notif1 = Notification.objects.create(
            user=test_user,
            order=test_order,
            recipient=test_user.email,
            event_type=Notification.EVENT_ORDER_PLACED,
            subject="Test Order Notification",
            status=Notification.STATUS_SENT,
        )
        # Create notification for other_user
        Notification.objects.create(
            user=other_user,
            recipient=other_user.email,
            event_type=Notification.EVENT_ACCOUNT_WELCOME,
            subject="Welcome Other",
            status=Notification.STATUS_SENT,
        )

        token = str(RefreshToken.for_user(test_user).access_token)
        client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        res = client.get("/api/v1/customer/notifications/")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 1
        assert data["results"][0]["public_id"] == str(notif1.public_id)


@pytest.mark.django_db
class TestAdminNotificationsAPI:
    """Verifies staff CMS notification delivery visibility and retry capabilities."""

    def test_staff_can_list_and_filter_notifications(self, client, staff_user, test_user, test_order):
        from rest_framework_simplejwt.tokens import RefreshToken

        notif = Notification.objects.create(
            user=test_user,
            order=test_order,
            recipient=test_user.email,
            event_type=Notification.EVENT_ORDER_SHIPPED,
            subject="Dispatched",
            status=Notification.STATUS_FAILED,
            error_message="Gateway timeout",
        )

        token = str(RefreshToken.for_user(staff_user).access_token)
        client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        # List
        res = client.get("/api/v1/admin/notifications/")
        assert res.status_code == 200
        assert res.json()["count"] >= 1

        # Filter by status failed
        res_filtered = client.get("/api/v1/admin/notifications/?status=failed")
        assert res_filtered.status_code == 200
        assert res_filtered.json()["results"][0]["public_id"] == str(notif.public_id)

    def test_staff_can_resend_notification(self, client, staff_user, test_user, test_order):
        from rest_framework_simplejwt.tokens import RefreshToken

        notif = Notification.objects.create(
            user=test_user,
            order=test_order,
            recipient=test_user.email,
            event_type=Notification.EVENT_ORDER_SHIPPED,
            subject="Dispatched",
            status=Notification.STATUS_FAILED,
            attempt_count=1,
            error_message="Network glitch",
        )

        token = str(RefreshToken.for_user(staff_user).access_token)
        client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        mail.outbox = []
        res = client.post(f"/api/v1/admin/notifications/{notif.public_id}/resend/")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == Notification.STATUS_SENT
        assert data["attempt_count"] == 2
        assert len(mail.outbox) == 1
