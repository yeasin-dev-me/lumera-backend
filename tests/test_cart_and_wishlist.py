"""Comprehensive tests for Cart and Wishlist domain."""
from decimal import Decimal
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.cart.models import Cart
from apps.categories.models import Category
from apps.products.models import Product
from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer_user():
    return User.objects.create_user(
        email="customer1@example.com",
        password="Password123!",
        first_name="Jane",
        last_name="Doe",
    )


@pytest.fixture
def customer_client(customer_user):
    client = APIClient()
    client.force_authenticate(user=customer_user)
    return client


@pytest.fixture
def other_customer():
    return User.objects.create_user(
        email="customer2@example.com",
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
def active_category():
    return Category.objects.create(
        name="Serums",
        slug="serums",
        status=Category.STATUS_ACTIVE,
    )


@pytest.fixture
def sample_product(active_category):
    return Product.objects.create(
        name="Luminous Glow Serum",
        slug="luminous-glow-serum",
        sku="LGS-001",
        category=active_category,
        price=Decimal("45.00"),
        discount_price=Decimal("38.50"),
        stock_quantity=10,
        status=Product.STATUS_ACTIVE,
        is_visible=True,
    )


@pytest.fixture
def luxury_cream(active_category):
    return Product.objects.create(
        name="Velvet Night Cream",
        slug="velvet-night-cream",
        sku="VNC-001",
        category=active_category,
        price=Decimal("999.90"),
        stock_quantity=5,
        status=Product.STATUS_ACTIVE,
        is_visible=True,
    )


# =====================================================================
# 1. Unauthenticated Cart & Wishlist Access
# =====================================================================

@pytest.mark.django_db
def test_unauthenticated_cart_access_rejected(api_client, sample_product):
    # GET cart
    resp = api_client.get("/api/v1/customer/cart/")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.json()["error"]["code"] in ["not_authenticated", "authentication_failed"]

    # POST add item
    resp_add = api_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 1},
        format="json",
    )
    assert resp_add.status_code == status.HTTP_401_UNAUTHORIZED

    # PATCH update item
    resp_patch = api_client.patch(
        f"/api/v1/customer/cart/items/{sample_product.public_id}/",
        data={"quantity": 2},
        format="json",
    )
    assert resp_patch.status_code == status.HTTP_401_UNAUTHORIZED

    # DELETE item
    resp_del = api_client.delete(f"/api/v1/customer/cart/items/{sample_product.public_id}/")
    assert resp_del.status_code == status.HTTP_401_UNAUTHORIZED

    # DELETE clear cart
    resp_clear = api_client.delete("/api/v1/customer/cart/")
    assert resp_clear.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_unauthenticated_wishlist_access_rejected(api_client, sample_product):
    # GET wishlist
    resp = api_client.get("/api/v1/customer/wishlist/")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # POST item
    resp_add = api_client.post(
        "/api/v1/customer/wishlist/items/",
        data={"product_id": str(sample_product.public_id)},
        format="json",
    )
    assert resp_add.status_code == status.HTTP_401_UNAUTHORIZED

    # DELETE item
    resp_del = api_client.delete(f"/api/v1/customer/wishlist/items/{sample_product.public_id}/")
    assert resp_del.status_code == status.HTTP_401_UNAUTHORIZED


# =====================================================================
# 2. Customer Cart Lifecycle & Business Rules
# =====================================================================

@pytest.mark.django_db
def test_authenticated_customer_empty_cart(customer_client):
    resp = customer_client.get("/api/v1/customer/cart/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["items"] == []
    assert data["item_count"] == 0
    assert data["subtotal"] == "0.00"
    assert data["total"] == "0.00"
    assert data["currency"] == "USD"
    assert data["has_unavailable_items"] is False


@pytest.mark.django_db
def test_add_valid_product_to_cart_and_authoritative_pricing(customer_client, sample_product):
    # Product has price=45.00, discount_price=38.50 -> effective_price is 38.50
    resp = customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 2},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["item_count"] == 2
    assert data["subtotal"] == "77.00"  # 38.50 * 2 = 77.00
    assert data["total"] == "77.00"
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["product"]["public_id"] == str(sample_product.public_id)
    assert item["quantity"] == 2
    assert item["unit_price"] == "38.50"
    assert item["line_total"] == "77.00"
    assert item["availability_status"] == "available"
    assert item["is_purchasable"] is True


@pytest.mark.django_db
def test_add_same_product_merges_quantity_authoritatively(customer_client, sample_product):
    # First add: 2 items
    customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 2},
        format="json",
    )

    # Second add: 3 items (stock is 10)
    resp = customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 3},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK  # Updated existing line
    data = resp.json()
    assert data["item_count"] == 5
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 5
    assert data["items"][0]["line_total"] == "192.50"  # 38.50 * 5 = 192.50
    assert data["subtotal"] == "192.50"

    # Verify database level uniqueness
    cart = Cart.objects.get(user__email="customer1@example.com")
    assert cart.items.count() == 1


@pytest.mark.django_db
def test_cart_quantity_validation_and_stock_limits(customer_client, sample_product):
    # 1. Quantity < 1 rejected
    resp_zero = customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 0},
        format="json",
    )
    assert resp_zero.status_code == status.HTTP_400_BAD_REQUEST

    # 2. Quantity > 20 rejected
    resp_over_20 = customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 21},
        format="json",
    )
    assert resp_over_20.status_code == status.HTTP_400_BAD_REQUEST

    # 3. Quantity exceeding available stock (stock=10, requested=12) -> 409 insufficient_stock
    resp_stock = customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 12},
        format="json",
    )
    assert resp_stock.status_code == status.HTTP_409_CONFLICT
    assert resp_stock.json()["error"]["code"] == "insufficient_stock"

    # 4. Adding more than available stock when already in cart
    customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 8},
        format="json",
    )
    # Adding 3 more makes 11 > 10
    resp_overflow = customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 3},
        format="json",
    )
    assert resp_overflow.status_code == status.HTTP_409_CONFLICT
    assert resp_overflow.json()["error"]["code"] == "insufficient_stock"


@pytest.mark.django_db
def test_cart_rejects_unavailable_and_nonexistent_products(customer_client, active_category):
    # 1. Nonexistent product UUID
    resp_404 = customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": "00000000-0000-0000-0000-000000000000", "quantity": 1},
        format="json",
    )
    assert resp_404.status_code == status.HTTP_404_NOT_FOUND

    # 2. Draft product rejected
    draft_prod = Product.objects.create(
        name="Draft Elixir",
        slug="draft-elixir",
        sku="DFT-002",
        category=active_category,
        price=Decimal("25.00"),
        stock_quantity=10,
        status=Product.STATUS_DRAFT,
        is_visible=True,
    )
    resp_draft = customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(draft_prod.public_id), "quantity": 1},
        format="json",
    )
    assert resp_draft.status_code == status.HTTP_404_NOT_FOUND

    # 3. Archived product rejected
    archived_prod = Product.objects.create(
        name="Archived Cream",
        slug="archived-cream",
        sku="ARC-002",
        category=active_category,
        price=Decimal("25.00"),
        stock_quantity=10,
        status=Product.STATUS_ARCHIVED,
        is_visible=True,
    )
    resp_arch = customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(archived_prod.public_id), "quantity": 1},
        format="json",
    )
    assert resp_arch.status_code == status.HTTP_404_NOT_FOUND

    # 4. Hidden product rejected
    hidden_prod = Product.objects.create(
        name="Hidden Oil",
        slug="hidden-oil",
        sku="HID-002",
        category=active_category,
        price=Decimal("25.00"),
        stock_quantity=10,
        status=Product.STATUS_ACTIVE,
        is_visible=False,
    )
    resp_hidden = customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(hidden_prod.public_id), "quantity": 1},
        format="json",
    )
    assert resp_hidden.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_update_cart_quantity_and_remove_item(customer_client, sample_product):
    # Add initial 2 items
    customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 2},
        format="json",
    )

    # 1. Update quantity to 4
    resp_patch = customer_client.patch(
        f"/api/v1/customer/cart/items/{sample_product.public_id}/",
        data={"quantity": 4},
        format="json",
    )
    assert resp_patch.status_code == status.HTTP_200_OK
    data = resp_patch.json()
    assert data["item_count"] == 4
    assert data["items"][0]["quantity"] == 4
    assert data["items"][0]["line_total"] == "154.00"  # 38.50 * 4 = 154.00
    assert data["subtotal"] == "154.00"

    # 2. Update to quantity exceeding stock -> 409
    resp_over = customer_client.patch(
        f"/api/v1/customer/cart/items/{sample_product.public_id}/",
        data={"quantity": 11},
        format="json",
    )
    assert resp_over.status_code == status.HTTP_409_CONFLICT
    assert resp_over.json()["error"]["code"] == "insufficient_stock"

    # 3. Remove item from cart
    resp_del = customer_client.delete(f"/api/v1/customer/cart/items/{sample_product.public_id}/")
    assert resp_del.status_code == status.HTTP_204_NO_CONTENT

    # Verify cart is now empty
    resp_cart = customer_client.get("/api/v1/customer/cart/")
    assert resp_cart.json()["item_count"] == 0

    # 4. Deleting again is idempotent
    resp_del2 = customer_client.delete(f"/api/v1/customer/cart/items/{sample_product.public_id}/")
    assert resp_del2.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_clear_cart(customer_client, sample_product, luxury_cream):
    # Add two different products
    customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 1},
        format="json",
    )
    customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(luxury_cream.public_id), "quantity": 1},
        format="json",
    )

    get_resp = customer_client.get("/api/v1/customer/cart/")
    assert get_resp.json()["item_count"] == 2

    # Clear cart
    clear_resp = customer_client.delete("/api/v1/customer/cart/")
    assert clear_resp.status_code == status.HTTP_204_NO_CONTENT

    # Verify empty
    get_resp2 = customer_client.get("/api/v1/customer/cart/")
    assert get_resp2.json()["item_count"] == 0
    assert get_resp2.json()["items"] == []


# =====================================================================
# 3. Authoritative Pricing & Decimal Calculations
# =====================================================================

@pytest.mark.django_db
def test_authoritative_decimal_pricing_precision(customer_client, luxury_cream):
    """Explicitly verify Decimal calculations: 999.90 * 3 = 2999.70 without floating point artifacts."""
    resp = customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(luxury_cream.public_id), "quantity": 3},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["items"][0]["unit_price"] == "999.90"
    assert data["items"][0]["line_total"] == "2999.70"
    assert data["subtotal"] == "2999.70"
    assert data["total"] == "2999.70"
    # Ensure no floating point precision issue like "2999.699999"
    assert "2999.70" in str(data["subtotal"])


@pytest.mark.django_db
def test_dynamic_cart_pricing_reflects_product_updates_automatically(customer_client, sample_product):
    """BR-10: Cart displays current prices (dynamic, no snapshot until order)."""
    # 1. Add product to cart when discount price is 38.50
    customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 2},
        format="json",
    )
    cart_resp = customer_client.get("/api/v1/customer/cart/")
    assert cart_resp.json()["subtotal"] == "77.00"

    # 2. Product discount price is updated in CMS / catalog to 30.00
    sample_product.discount_price = Decimal("30.00")
    sample_product.save()

    # 3. Cart automatically reflects updated price on read
    cart_resp2 = customer_client.get("/api/v1/customer/cart/")
    assert cart_resp2.json()["items"][0]["unit_price"] == "30.00"
    assert cart_resp2.json()["items"][0]["line_total"] == "60.00"
    assert cart_resp2.json()["subtotal"] == "60.00"


# =====================================================================
# 4. Inactive Product Dynamic Cart Status
# =====================================================================

@pytest.mark.django_db
def test_cart_item_becomes_unavailable_when_product_archived(customer_client, sample_product):
    """When a product in cart is archived, it becomes unavailable and is excluded from subtotal."""
    customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 2},
        format="json",
    )

    # Archive the product
    sample_product.status = Product.STATUS_ARCHIVED
    sample_product.save()

    # Cart read shows it as unavailable and excludes it from subtotal
    resp = customer_client.get("/api/v1/customer/cart/")
    data = resp.json()
    assert data["has_unavailable_items"] is True
    assert data["items"][0]["availability_status"] == "unavailable"
    assert data["items"][0]["is_purchasable"] is False
    assert data["subtotal"] == "0.00"

    # Attempting to update quantity of unavailable item returns 409 product_unavailable
    patch_resp = customer_client.patch(
        f"/api/v1/customer/cart/items/{sample_product.public_id}/",
        data={"quantity": 3},
        format="json",
    )
    assert patch_resp.status_code == status.HTTP_409_CONFLICT
    assert patch_resp.json()["error"]["code"] == "product_unavailable"

    # Removing it is allowed
    del_resp = customer_client.delete(f"/api/v1/customer/cart/items/{sample_product.public_id}/")
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT


# =====================================================================
# 5. Customer Isolation
# =====================================================================

@pytest.mark.django_db
def test_customer_cart_and_wishlist_isolation(customer_client, other_client, sample_product):
    """Customer A and Customer B have completely isolated carts and wishlists."""
    # 1. Customer A adds item to cart & wishlist
    customer_client.post(
        "/api/v1/customer/cart/items/",
        data={"product_id": str(sample_product.public_id), "quantity": 3},
        format="json",
    )
    customer_client.post(
        "/api/v1/customer/wishlist/items/",
        data={"product_id": str(sample_product.public_id)},
        format="json",
    )

    # 2. Customer B checks cart & wishlist -> completely empty
    cart_b = other_client.get("/api/v1/customer/cart/").json()
    assert cart_b["item_count"] == 0
    assert cart_b["items"] == []

    wish_b = other_client.get("/api/v1/customer/wishlist/").json()
    assert wish_b["item_count"] == 0
    assert wish_b["items"] == []

    # 3. Customer B attempts to remove Customer A's item -> only affects B's cart
    other_client.delete(f"/api/v1/customer/cart/items/{sample_product.public_id}/")

    # Customer A's cart is intact
    cart_a = customer_client.get("/api/v1/customer/cart/").json()
    assert cart_a["item_count"] == 3


# =====================================================================
# 6. Wishlist Lifecycle & Business Rules
# =====================================================================

@pytest.mark.django_db
def test_wishlist_lifecycle_and_duplicate_prevention(customer_client, sample_product):
    # 1. Initial wishlist is empty
    resp_empty = customer_client.get("/api/v1/customer/wishlist/")
    assert resp_empty.status_code == status.HTTP_200_OK
    assert resp_empty.json()["items"] == []
    assert resp_empty.json()["item_count"] == 0

    # 2. Add product to wishlist
    resp_add = customer_client.post(
        "/api/v1/customer/wishlist/items/",
        data={"product_id": str(sample_product.public_id)},
        format="json",
    )
    assert resp_add.status_code == status.HTTP_201_CREATED
    data = resp_add.json()
    assert data["item_count"] == 1
    assert data["items"][0]["product"]["public_id"] == str(sample_product.public_id)
    assert data["items"][0]["is_available"] is True

    # 3. Duplicate product add rejected with 409 Conflict (BR-10d)
    resp_dup = customer_client.post(
        "/api/v1/customer/wishlist/items/",
        data={"product_id": str(sample_product.public_id)},
        format="json",
    )
    assert resp_dup.status_code == status.HTTP_409_CONFLICT
    assert resp_dup.json()["error"]["code"] == "conflict"

    # 4. Remove item from wishlist
    resp_del = customer_client.delete(f"/api/v1/customer/wishlist/items/{sample_product.public_id}/")
    assert resp_del.status_code == status.HTTP_204_NO_CONTENT

    # 5. Verify wishlist is empty
    resp_after = customer_client.get("/api/v1/customer/wishlist/")
    assert resp_after.json()["item_count"] == 0

    # 6. Deleting again is idempotent
    resp_del2 = customer_client.delete(f"/api/v1/customer/wishlist/items/{sample_product.public_id}/")
    assert resp_del2.status_code == status.HTTP_204_NO_CONTENT
