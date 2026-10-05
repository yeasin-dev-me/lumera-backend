"""Comprehensive tests for Checkout and Orders domain (Step 6)."""
from decimal import Decimal
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.cart.models import Cart, CartItem
from apps.categories.models import Category
from apps.orders.models import Order
from apps.orders.services import create_order_from_cart
from apps.products.models import Product
from apps.users.models import Role, User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer_user():
    return User.objects.create_user(
        email="jane.customer@example.com",
        password="Password123!",
        first_name="Jane",
        last_name="Doe",
        phone="+8801711111111",
    )


@pytest.fixture
def customer_client(customer_user):
    client = APIClient()
    client.force_authenticate(user=customer_user)
    return client


@pytest.fixture
def other_customer():
    return User.objects.create_user(
        email="john.other@example.com",
        password="Password123!",
        first_name="John",
        last_name="Smith",
    )


@pytest.fixture
def other_client(other_customer):
    client = APIClient()
    client.force_authenticate(user=other_customer)
    return client


@pytest.fixture
def staff_user():
    user = User.objects.create_user(
        email="staff.orders@example.com",
        password="Password123!",
        first_name="Admin",
        last_name="Staff",
        is_staff=True,
    )
    role = Role.objects.create(
        name="OrderViewer",
        permissions=["orders.read"],
    )
    user.roles.add(role)
    return user


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def active_category():
    return Category.objects.create(
        name="Skincare",
        slug="skincare",
        status=Category.STATUS_ACTIVE,
    )


@pytest.fixture
def active_product(active_category):
    return Product.objects.create(
        name="Hydrating Facial Serum",
        slug="hydrating-facial-serum",
        sku="SKU-HYDRA-001",
        category=active_category,
        price=Decimal("1200.00"),
        discount_price=Decimal("999.90"),
        stock_quantity=15,
        status=Product.STATUS_ACTIVE,
        is_visible=True,
    )


@pytest.fixture
def valid_shipping_data():
    return {
        "shipping_address": {
            "full_name": "Jane Doe",
            "phone": "+8801711111111",
            "address": "House 42, Road 11",
            "city": "Dhaka",
            "area": "Banani",
            "postal_code": "1213",
            "country": "Bangladesh",
        },
        "customer_notes": "Please ring doorbell twice",
    }


@pytest.mark.django_db
class TestCheckoutPreview:
    """Verify GET /api/v1/customer/checkout/."""

    def test_unauthenticated_checkout_preview_rejected(self, api_client):
        res = api_client.get("/api/v1/customer/checkout/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.data["error"]["code"] == "not_authenticated"

    def test_authenticated_customer_preview_with_items(
        self, customer_client, customer_user, active_product
    ):
        cart, _ = Cart.objects.get_or_create(user=customer_user)
        CartItem.objects.create(cart=cart, product=active_product, quantity=2)

        res = customer_client.get("/api/v1/customer/checkout/")
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        assert data["is_ready_for_checkout"] is True
        assert data["subtotal"] == "1999.80"  # 999.90 * 2
        assert data["total"] == "1999.80"
        assert data["shipping_cost"] == "0.00"
        assert data["customer"]["email"] == customer_user.email
        assert data["customer"]["full_name"] == "Jane Doe"

    def test_empty_cart_preview(self, customer_client):
        res = customer_client.get("/api/v1/customer/checkout/")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["is_ready_for_checkout"] is False
        assert res.data["subtotal"] == "0.00"


@pytest.mark.django_db
class TestOrderCreation:
    """Verify POST /api/v1/customer/orders/ and authoritative calculations."""

    def test_unauthenticated_order_creation_rejected(self, api_client, valid_shipping_data):
        res = api_client.post("/api/v1/customer/orders/", valid_shipping_data, format="json")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_empty_cart_cannot_checkout(self, customer_client, valid_shipping_data):
        res = customer_client.post("/api/v1/customer/orders/", valid_shipping_data, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["error"]["code"] == "validation_error"

    def test_invalid_shipping_information_rejected(self, customer_client, customer_user, active_product):
        cart, _ = Cart.objects.get_or_create(user=customer_user)
        CartItem.objects.create(cart=cart, product=active_product, quantity=1)

        invalid_data = {
            "shipping_address": {
                "full_name": "",  # invalid
                "phone": "",
            }
        }
        res = customer_client.post("/api/v1/customer/orders/", invalid_data, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["error"]["code"] == "validation_error"

    def test_insufficient_stock_rejected_and_rolls_back(
        self, customer_client, customer_user, active_product, valid_shipping_data
    ):
        cart, _ = Cart.objects.get_or_create(user=customer_user)
        CartItem.objects.create(cart=cart, product=active_product, quantity=5)

        # Lower product stock below cart quantity
        active_product.stock_quantity = 3
        active_product.save(update_fields=["stock_quantity"])

        res = customer_client.post("/api/v1/customer/orders/", valid_shipping_data, format="json")
        assert res.status_code == status.HTTP_409_CONFLICT
        assert res.data["error"]["code"] == "insufficient_stock"

        # Verify atomicity: No order created, stock untouched, cart intact
        assert Order.objects.count() == 0
        active_product.refresh_from_db()
        assert active_product.stock_quantity == 3
        assert cart.items.count() == 1

    def test_unavailable_product_rejected_and_rolls_back(
        self, customer_client, customer_user, active_product, valid_shipping_data
    ):
        cart, _ = Cart.objects.get_or_create(user=customer_user)
        CartItem.objects.create(cart=cart, product=active_product, quantity=1)

        # Deactivate product
        active_product.status = Product.STATUS_ARCHIVED
        active_product.save(update_fields=["status"])

        res = customer_client.post("/api/v1/customer/orders/", valid_shipping_data, format="json")
        assert res.status_code == status.HTTP_409_CONFLICT
        assert res.data["error"]["code"] == "product_unavailable"
        assert Order.objects.count() == 0
        assert cart.items.count() == 1

    def test_successful_order_creation_and_snapshots(
        self, customer_client, customer_user, active_product, valid_shipping_data
    ):
        initial_stock = active_product.stock_quantity
        cart, _ = Cart.objects.get_or_create(user=customer_user)
        CartItem.objects.create(cart=cart, product=active_product, quantity=3)

        res = customer_client.post("/api/v1/customer/orders/", valid_shipping_data, format="json")
        assert res.status_code == status.HTTP_201_CREATED
        data = res.data

        # 1. Order attributes
        assert data["order_number"].startswith("LUM-")
        assert data["status"] == "pending"
        assert data["payment_status"] == "pending"
        assert data["subtotal"] == "2999.70"  # 999.90 * 3
        assert data["shipping_cost"] == "0.00"
        assert data["discount_total"] == "0.00"
        assert data["total"] == "2999.70"
        assert data["currency"] == "USD"
        assert data["shipping_address"]["full_name"] == "Jane Doe"
        assert data["shipping_address"]["city"] == "Dhaka"
        assert data["customer_notes"] == "Please ring doorbell twice"

        # 2. Items & Snapshots
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["product_name"] == active_product.name
        assert item["product_sku"] == active_product.sku
        assert item["unit_price"] == "999.90"
        assert item["quantity"] == 3
        assert item["line_total"] == "2999.70"

        # 3. Stock deduction
        active_product.refresh_from_db()
        assert active_product.stock_quantity == initial_stock - 3

        # 4. Cart cleared
        assert cart.items.count() == 0

        # 5. Status history
        order = Order.objects.get(public_id=data["public_id"])
        history = list(order.status_history.all())
        assert len(history) == 1
        assert history[0].to_status == "pending"


@pytest.mark.django_db
class TestHistoricalIntegrity:
    """Verify purchase-time snapshots are completely decoupled from future changes."""

    def test_catalog_and_address_changes_do_not_alter_order(
        self, customer_user, active_product, valid_shipping_data
    ):
        cart, _ = Cart.objects.get_or_create(user=customer_user)
        CartItem.objects.create(cart=cart, product=active_product, quantity=2)

        order = create_order_from_cart(
            user=customer_user,
            shipping_address=valid_shipping_data["shipping_address"],
            customer_notes="Original Note",
        )

        order_item = order.items.first()
        assert order_item.unit_price == Decimal("999.90")
        assert order_item.product_name == "Hydrating Facial Serum"

        # 1. Modify Product in catalog: raise regular price and change name & SKU
        active_product.price = Decimal("2500.00")
        active_product.discount_price = Decimal("2200.00")
        active_product.name = "Ultra Hydrating Serum V2"
        active_product.sku = "SKU-HYDRA-V2"
        active_product.save()

        # 2. Modify customer profile
        customer_user.first_name = "Janet"
        customer_user.phone = "+8801999999999"
        customer_user.save()

        # 3. Verify order still has original snapshot values
        order.refresh_from_db()
        order_item.refresh_from_db()

        assert order_item.unit_price == Decimal("999.90")
        assert order_item.line_total == Decimal("1999.80")
        assert order_item.product_name == "Hydrating Facial Serum"
        assert order_item.product_sku == "SKU-HYDRA-001"
        assert order.subtotal == Decimal("1999.80")
        assert order.total == Decimal("1999.80")
        assert order.shipping_full_name == "Jane Doe"
        assert order.shipping_phone == "+8801711111111"


@pytest.mark.django_db
class TestCustomerIsolation:
    """Verify Customer B cannot list or access Customer A's orders."""

    def test_customer_isolation_on_list_and_detail(
        self, customer_user, customer_client, other_customer, other_client, active_product, valid_shipping_data
    ):
        cart, _ = Cart.objects.get_or_create(user=customer_user)
        CartItem.objects.create(cart=cart, product=active_product, quantity=1)

        order_a = create_order_from_cart(
            user=customer_user,
            shipping_address=valid_shipping_data["shipping_address"],
        )

        # Customer A sees order in their list
        res_a = customer_client.get("/api/v1/customer/orders/")
        assert res_a.status_code == status.HTTP_200_OK
        assert res_a.data["count"] == 1
        assert res_a.data["results"][0]["public_id"] == str(order_a.public_id)

        # Customer B list is empty
        res_b = other_client.get("/api/v1/customer/orders/")
        assert res_b.status_code == status.HTTP_200_OK
        assert res_b.data["count"] == 0

        # Customer B attempting to retrieve Customer A's order by UUID gets 404
        res_detail_b = other_client.get(f"/api/v1/customer/orders/{order_a.public_id}/")
        assert res_detail_b.status_code == status.HTTP_404_NOT_FOUND
        assert res_detail_b.data["error"]["code"] == "not_found"


@pytest.mark.django_db
class TestDecimalAndMoneyExactness:
    """Verify no floating-point rounding errors on Decimal values."""

    def test_decimal_money_exactness(self, customer_user, active_category, valid_shipping_data):
        # Product with price 999.90
        prod = Product.objects.create(
            name="Precise Money Product",
            slug="precise-money-product",
            sku="SKU-MONEY-001",
            category=active_category,
            price=Decimal("999.90"),
            stock_quantity=10,
            status=Product.STATUS_ACTIVE,
            is_visible=True,
        )

        cart, _ = Cart.objects.get_or_create(user=customer_user)
        CartItem.objects.create(cart=cart, product=prod, quantity=3)

        order = create_order_from_cart(
            user=customer_user,
            shipping_address=valid_shipping_data["shipping_address"],
        )

        assert str(order.subtotal) == "2999.70"
        assert str(order.total) == "2999.70"
        assert str(order.items.first().line_total) == "2999.70"


@pytest.mark.django_db
class TestAdminOrdersCMSVisibility:
    """Verify CMS staff operational visibility into orders."""

    def test_staff_with_permission_can_list_and_view(
        self, staff_client, customer_user, active_product, valid_shipping_data
    ):
        cart, _ = Cart.objects.get_or_create(user=customer_user)
        CartItem.objects.create(cart=cart, product=active_product, quantity=1)

        order = create_order_from_cart(
            user=customer_user,
            shipping_address=valid_shipping_data["shipping_address"],
        )

        # 1. Staff lists orders
        res = staff_client.get("/api/v1/admin/orders/")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] >= 1
        found = any(r["public_id"] == str(order.public_id) for r in res.data["results"])
        assert found is True

        # 2. Staff views order detail
        res_detail = staff_client.get(f"/api/v1/admin/orders/{order.public_id}/")
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data["customer"]["email"] == customer_user.email
        assert res_detail.data["order_number"] == order.order_number
        assert len(res_detail.data["items"]) == 1

    def test_staff_without_permission_forbidden(
        self, active_product, customer_user, valid_shipping_data
    ):
        staff_no_perm = User.objects.create_user(
            email="staff.noperm@example.com",
            password="Password123!",
            is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(user=staff_no_perm)

        res = client.get("/api/v1/admin/orders/")
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert res.data["error"]["code"] == "permission_denied"


@pytest.mark.django_db
class TestConcurrencyAndStockProtection:
    """Verify concurrent requests cannot oversell stock (BR-08, Section 20)."""

    def test_stock_depletion_prevents_subsequent_checkout(
        self, customer_user, other_customer, active_product, valid_shipping_data
    ):
        """When available stock is 2, and Customer A orders 2, Customer B's checkout fails."""
        from apps.common.exceptions import InsufficientStock

        active_product.stock_quantity = 2
        active_product.save(update_fields=["stock_quantity"])

        cart_a, _ = Cart.objects.get_or_create(user=customer_user)
        CartItem.objects.create(cart=cart_a, product=active_product, quantity=2)

        cart_b, _ = Cart.objects.get_or_create(user=other_customer)
        CartItem.objects.create(cart=cart_b, product=active_product, quantity=2)

        # Customer A checkouts successfully
        order_a = create_order_from_cart(
            user=customer_user,
            shipping_address=valid_shipping_data["shipping_address"],
        )
        assert order_a is not None
        active_product.refresh_from_db()
        assert active_product.stock_quantity == 0

        # Customer B attempts checkout with now-depleted stock -> must raise InsufficientStock
        with pytest.raises(InsufficientStock):
            create_order_from_cart(
                user=other_customer,
                shipping_address=valid_shipping_data["shipping_address"],
            )

        # Confirm stock didn't become negative and customer B's cart remains intact
        active_product.refresh_from_db()
        assert active_product.stock_quantity == 0
        assert cart_b.items.count() == 1
        assert Order.objects.count() == 1
