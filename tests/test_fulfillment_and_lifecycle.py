"""Comprehensive vertical-slice tests for Fulfillment, Order Lifecycle, and Notifications (Step 8, ADR-0015)."""
from decimal import Decimal
from unittest.mock import patch
import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client
from apps.categories.models import Category
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.orders.services import cancel_order, transition_order_status
from apps.products.models import Product

User = get_user_model()


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def customer_user(db):
    return User.objects.create_user(
        email="customer.step8@lumera.local",
        password="CustomerPassword123!",
        first_name="Step 8",
        last_name="Customer",
    )


@pytest.fixture
def other_customer(db):
    return User.objects.create_user(
        email="other.step8@lumera.local",
        password="CustomerPassword123!",
        first_name="Other",
        last_name="Customer",
    )


@pytest.fixture
def staff_user(db):
    user = User.objects.create_user(
        email="staff.step8@lumera.local",
        password="StaffPassword123!",
        first_name="Fulfillment",
        last_name="Staff",
        is_staff=True,
    )
    from apps.users.models import Role
    role, _ = Role.objects.get_or_create(
        name="OrderFulfillmentManager",
        defaults={"permissions": ["orders.read", "orders.manage"]},
    )
    user.roles.add(role)
    return user


@pytest.fixture
def staff_readonly(db):
    user = User.objects.create_user(
        email="readonly.step8@lumera.local",
        password="StaffPassword123!",
        first_name="Readonly",
        last_name="Staff",
        is_staff=True,
    )
    from apps.users.models import Role
    role, _ = Role.objects.get_or_create(
        name="OrderViewer",
        defaults={"permissions": ["orders.read"]},
    )
    user.roles.add(role)
    return user


@pytest.fixture
def customer_token(customer_user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(customer_user)
    return str(refresh.access_token)


@pytest.fixture
def other_token(other_customer):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(other_customer)
    return str(refresh.access_token)


@pytest.fixture
def staff_token(staff_user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(staff_user)
    refresh["aud"] = "cms"
    return str(refresh.access_token)


@pytest.fixture
def staff_readonly_token(staff_readonly):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(staff_readonly)
    refresh["aud"] = "cms"
    return str(refresh.access_token)


@pytest.fixture
def sample_product(db):
    cat = Category.objects.create(name="Fulfillment Cat", slug="fulfillment-cat")
    return Product.objects.create(
        name="Fulfillment Product",
        slug="fulfillment-product",
        sku="SKU-STEP8-FULFILL",
        category=cat,
        price=Decimal("150.00"),
        stock_quantity=20,
        status=Product.STATUS_ACTIVE,
    )


@pytest.fixture
def sample_order(db, customer_user, sample_product):
    order = Order.objects.create(
        order_number="LUM-20261006-FLL001",
        user=customer_user,
        status=Order.STATUS_PENDING,
        payment_status=Order.PAYMENT_PENDING,
        currency="USD",
        subtotal=Decimal("300.00"),
        shipping_cost=Decimal("0.00"),
        discount_total=Decimal("0.00"),
        total=Decimal("300.00"),
        shipping_full_name="Step 8 Customer",
        shipping_phone="01700000000",
        shipping_address_line1="House 1, Road 2",
        shipping_city="Dhaka",
        shipping_country="Bangladesh",
    )
    OrderItem.objects.create(
        order=order,
        product=sample_product,
        product_name=sample_product.name,
        product_sku=sample_product.sku,
        unit_price=Decimal("150.00"),
        quantity=2,
        line_total=Decimal("300.00"),
    )
    OrderStatusHistory.objects.create(
        order=order,
        from_status="",
        to_status=Order.STATUS_PENDING,
        changed_by=customer_user,
        reason="Order placed",
    )
    return order


@pytest.mark.django_db
class TestOrderLifecycleAndFulfillment:
    """Tests authoritative state machine transitions and fulfillment operations."""

    def test_unpaid_order_cannot_enter_processing(self, sample_order, staff_user):
        """Unpaid order cannot transition to processing or shipped (ADR-0015)."""
        from apps.common.exceptions import ConflictError
        assert sample_order.payment_status == Order.PAYMENT_PENDING

        # First confirm order
        transition_order_status(sample_order, Order.STATUS_CONFIRMED, user=staff_user)

        with pytest.raises(ConflictError) as exc_info:
            transition_order_status(sample_order, Order.STATUS_PROCESSING, user=staff_user)
        assert "must be paid" in str(exc_info.value)

    def test_paid_order_complete_fulfillment_lifecycle(self, sample_order, staff_user):
        """Paid order legally moves: pending -> confirmed -> processing -> shipped -> delivered."""
        # 1. Mark paid & confirmed
        sample_order.payment_status = Order.PAYMENT_PAID
        sample_order.save(update_fields=["payment_status"])

        order = transition_order_status(sample_order, Order.STATUS_CONFIRMED, user=staff_user, reason="Payment received")
        assert order.status == Order.STATUS_CONFIRMED

        # 2. Confirmed -> Processing
        order = transition_order_status(order, Order.STATUS_PROCESSING, user=staff_user, reason="Warehouse picking")
        assert order.status == Order.STATUS_PROCESSING

        # 3. Processing -> Shipped (requires courier and tracking)
        order = transition_order_status(
            order,
            Order.STATUS_SHIPPED,
            user=staff_user,
            reason="Dispatched with courier",
            courier="Steadfast",
            tracking_number="ST-998877",
            tracking_url="https://steadfast.com.bd/t/ST-998877",
        )
        assert order.status == Order.STATUS_SHIPPED
        assert order.courier == "Steadfast"
        assert order.tracking_number == "ST-998877"
        assert order.shipped_at is not None

        # 4. Shipped -> Delivered
        order = transition_order_status(order, Order.STATUS_DELIVERED, user=staff_user, reason="Customer received package")
        assert order.status == Order.STATUS_DELIVERED
        assert order.delivered_at is not None

        # 5. Check audit history
        history = list(order.status_history.order_by("created_at"))
        assert len(history) == 5  # placed + 4 transitions
        assert history[-1].to_status == Order.STATUS_DELIVERED
        assert history[-1].actor_type == "staff"

    def test_shipped_requires_courier_and_tracking(self, sample_order, staff_user):
        """Transitioning to shipped without courier or tracking is rejected with ValidationError."""
        from rest_framework import exceptions
        sample_order.payment_status = Order.PAYMENT_PAID
        sample_order.status = Order.STATUS_PROCESSING
        sample_order.save()

        with pytest.raises(exceptions.ValidationError) as exc:
            transition_order_status(sample_order, Order.STATUS_SHIPPED, user=staff_user, courier="", tracking_number="")
        assert "courier" in exc.value.detail

    def test_illegal_state_skips_rejected(self, sample_order, staff_user):
        """Attempting to jump from pending directly to shipped or delivered is rejected with 409 Conflict."""
        from apps.common.exceptions import ConflictError
        sample_order.payment_status = Order.PAYMENT_PAID
        sample_order.save()

        with pytest.raises(ConflictError):
            transition_order_status(sample_order, Order.STATUS_SHIPPED, user=staff_user, courier="Steadfast", tracking_number="TRK123")

        with pytest.raises(ConflictError):
            transition_order_status(sample_order, Order.STATUS_DELIVERED, user=staff_user)

    def test_terminal_states_are_immutable(self, sample_order, staff_user):
        """Delivered and cancelled states cannot be transitioned to any other state."""
        from apps.common.exceptions import ConflictError
        sample_order.status = Order.STATUS_DELIVERED
        sample_order.save()

        with pytest.raises(ConflictError):
            transition_order_status(sample_order, Order.STATUS_PROCESSING, user=staff_user)

        sample_order.status = Order.STATUS_CANCELLED
        sample_order.save()

        with pytest.raises(ConflictError):
            transition_order_status(sample_order, Order.STATUS_PENDING, user=staff_user)

    def test_fulfillment_does_not_deduct_inventory(self, sample_order, sample_product, staff_user):
        """Progression through processing, shipped, and delivered leaves stock quantity unchanged."""
        initial_stock = sample_product.stock_quantity
        sample_order.payment_status = Order.PAYMENT_PAID
        sample_order.save()

        transition_order_status(sample_order, Order.STATUS_CONFIRMED, user=staff_user)
        transition_order_status(sample_order, Order.STATUS_PROCESSING, user=staff_user)
        transition_order_status(sample_order, Order.STATUS_SHIPPED, user=staff_user, courier="DHL", tracking_number="DHL-1")
        transition_order_status(sample_order, Order.STATUS_DELIVERED, user=staff_user)

        sample_product.refresh_from_db()
        assert sample_product.stock_quantity == initial_stock

    def test_order_cancellation_restores_inventory(self, sample_order, sample_product, customer_user):
        """Cancelling an order restores product stock atomically (ADR-0015)."""
        initial_stock = sample_product.stock_quantity
        # OrderItem has quantity 2
        order = cancel_order(sample_order, user=customer_user, reason="Customer cancelled")
        assert order.status == Order.STATUS_CANCELLED

        sample_product.refresh_from_db()
        assert sample_product.stock_quantity == initial_stock + 2

    def test_customer_cannot_cancel_paid_order(self, sample_order, customer_user):
        """Customer cannot cancel paid or confirmed order via self-serve API."""
        from apps.common.exceptions import ConflictError
        sample_order.payment_status = Order.PAYMENT_PAID
        sample_order.status = Order.STATUS_CONFIRMED
        sample_order.save()

        with pytest.raises(ConflictError):
            cancel_order(sample_order, user=customer_user, reason="Self-serve attempt")

    def test_staff_can_cancel_paid_order_without_altering_payment(self, sample_order, staff_user, sample_product):
        """Staff cancellation of paid order marks status cancelled but leaves payment_status paid (no auto refund)."""
        sample_order.payment_status = Order.PAYMENT_PAID
        sample_order.status = Order.STATUS_PROCESSING
        sample_order.save()

        order = cancel_order(sample_order, user=staff_user, reason="Warehouse out of stock")
        assert order.status == Order.STATUS_CANCELLED
        assert order.payment_status == Order.PAYMENT_PAID  # Payment remains paid per ADR-0015


@pytest.mark.django_db
class TestAdminFulfillmentAPI:
    """Tests staff transition and fulfillment endpoints in CMS."""

    def test_staff_transition_endpoint_success(self, api_client, sample_order, staff_token):
        sample_order.payment_status = Order.PAYMENT_PAID
        sample_order.save()

        # Step 1: Confirmed
        res1 = api_client.post(
            f"/api/v1/admin/orders/{sample_order.public_id}/transition/",
            data={"to_status": "confirmed", "reason": "Staff approved"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {staff_token}",
        )
        assert res1.status_code == 200
        assert res1.json()["status"] == "confirmed"

        # Step 2: Processing
        res2 = api_client.post(
            f"/api/v1/admin/orders/{sample_order.public_id}/transition/",
            data={"to_status": "processing", "reason": "Packing initiated"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {staff_token}",
        )
        assert res2.status_code == 200
        assert res2.json()["status"] == "processing"

    def test_staff_transition_unpaid_order_fails(self, api_client, sample_order, staff_token):
        """Unpaid order cannot be transitioned to processing via API (409 Conflict)."""
        sample_order.status = Order.STATUS_CONFIRMED
        sample_order.save()

        res = api_client.post(
            f"/api/v1/admin/orders/{sample_order.public_id}/transition/",
            data={"to_status": "processing"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {staff_token}",
        )
        assert res.status_code == 409
        assert "must be paid" in res.json()["error"]["message"]

    def test_staff_fulfillment_update_endpoint(self, api_client, sample_order, staff_token):
        """Staff can update courier and tracking info without changing status."""
        res = api_client.patch(
            f"/api/v1/admin/orders/{sample_order.public_id}/fulfillment/",
            data={
                "courier": "Pathao",
                "tracking_number": "PTH-123456",
                "tracking_url": "https://pathao.com/track/PTH-123456",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {staff_token}",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["courier"] == "Pathao"
        assert data["tracking_number"] == "PTH-123456"

    def test_readonly_staff_cannot_transition(self, api_client, sample_order, staff_readonly_token):
        """Staff without orders.manage receives 403 Forbidden on transition."""
        res = api_client.post(
            f"/api/v1/admin/orders/{sample_order.public_id}/transition/",
            data={"to_status": "confirmed"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {staff_readonly_token}",
        )
        assert res.status_code == 403


@pytest.mark.django_db
class TestCustomerOrderFulfillmentAPI:
    """Tests customer self-serve cancellation and timeline visibility."""

    def test_customer_can_cancel_own_unpaid_order(self, api_client, sample_order, customer_token, sample_product):
        initial_stock = sample_product.stock_quantity
        res = api_client.post(
            f"/api/v1/customer/orders/{sample_order.public_id}/cancel/",
            data={"reason": "Customer changed mind"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {customer_token}",
        )
        assert res.status_code == 200
        assert res.json()["status"] == "cancelled"

        sample_product.refresh_from_db()
        assert sample_product.stock_quantity == initial_stock + 2

    def test_customer_cannot_cancel_other_customer_order(self, api_client, sample_order, other_token):
        """Customer A cannot cancel Customer B's order (404 Not Found / Customer Isolation)."""
        res = api_client.post(
            f"/api/v1/customer/orders/{sample_order.public_id}/cancel/",
            data={"reason": "Attacker trying to cancel"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {other_token}",
        )
        assert res.status_code == 404

    def test_customer_order_timeline_view(self, api_client, sample_order, customer_token, staff_user):
        """Timeline returns chronological status changes with actor_type."""
        sample_order.payment_status = Order.PAYMENT_PAID
        sample_order.save()
        transition_order_status(sample_order, Order.STATUS_CONFIRMED, user=staff_user, reason="Approved")

        res = api_client.get(
            f"/api/v1/customer/orders/{sample_order.public_id}/timeline/",
            HTTP_AUTHORIZATION=f"Bearer {customer_token}",
        )
        assert res.status_code == 200
        timeline = res.json()
        assert len(timeline) == 2
        assert timeline[0]["to_status"] == "pending"
        assert timeline[0]["actor_type"] == "customer"
        assert timeline[1]["to_status"] == "confirmed"
        assert timeline[1]["actor_type"] == "staff"


@pytest.mark.django_db
class TestNotificationDomain:
    """Tests notification dispatch, fail-safe error isolation, and idempotency (ADR-0015)."""

    def test_transition_dispatches_notification_email(self, sample_order, staff_user):
        mail.outbox.clear()
        sample_order.payment_status = Order.PAYMENT_PAID
        sample_order.save()

        transition_order_status(sample_order, Order.STATUS_CONFIRMED, user=staff_user)

        assert len(mail.outbox) == 1
        assert "Payment Confirmed" in mail.outbox[0].subject
        assert sample_order.user.email in mail.outbox[0].to

        notif = Notification.objects.filter(order=sample_order, event_type=Notification.EVENT_PAYMENT_CONFIRMED).first()
        assert notif is not None
        assert notif.status == Notification.STATUS_SENT

    def test_notification_failure_does_not_rollback_order(self, sample_order, staff_user):
        """Failure in email provider logs failed notification but does NOT abort business transaction."""
        sample_order.payment_status = Order.PAYMENT_PAID
        sample_order.save()

        with patch("apps.notifications.services.send_mail", side_effect=Exception("SMTP Connection Refused")):
            order = transition_order_status(sample_order, Order.STATUS_CONFIRMED, user=staff_user)

        # Order must remain confirmed!
        assert order.status == Order.STATUS_CONFIRMED

        notif = Notification.objects.filter(order=sample_order, event_type=Notification.EVENT_PAYMENT_CONFIRMED).first()
        assert notif is not None
        assert notif.status == Notification.STATUS_FAILED
        assert "SMTP Connection Refused" in notif.error_message

    def test_notification_idempotency(self, sample_order):
        """Repeated dispatch for same order and event_type does not create duplicate notifications."""
        from apps.notifications.services import send_order_notification
        n1 = send_order_notification(sample_order, Notification.EVENT_ORDER_PROCESSING)
        n2 = send_order_notification(sample_order, Notification.EVENT_ORDER_PROCESSING)

        assert n1.id == n2.id
        assert Notification.objects.filter(order=sample_order, event_type=Notification.EVENT_ORDER_PROCESSING).count() == 1
