from decimal import Decimal
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.categories.models import Category
from apps.products.models import Product
from apps.users.models import Role, User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def product_admin_client():
    client = APIClient()
    user = User.objects.create_user(
        email="prod_admin@example.com",
        password="StaffPassword123!",
        is_staff=True,
    )
    role = Role.objects.create(
        name="product_manager",
        permissions=["products.read", "products.write", "products.delete"],
    )
    user.roles.add(role)
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def readonly_staff_client():
    client = APIClient()
    user = User.objects.create_user(
        email="readonly_prod@example.com",
        password="StaffPassword123!",
        is_staff=True,
    )
    role = Role.objects.create(
        name="product_viewer",
        permissions=["products.read"],
    )
    user.roles.add(role)
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_product_storefront_visibility_rules(api_client):
    """BR-04: Only products with status=active, is_visible=true, and active category are visible."""
    cat_active = Category.objects.create(name="Serums", slug="serums", status=Category.STATUS_ACTIVE)
    cat_archived = Category.objects.create(name="Old Toners", slug="old-toners", status=Category.STATUS_ARCHIVED)

    # 1. Active & visible in active category -> visible
    p1 = Product.objects.create(
        name="Vitamin C Serum",
        slug="vitamin-c-serum",
        sku="VITC-01",
        category=cat_active,
        price=Decimal("45.00"),
        stock_quantity=20,
        status=Product.STATUS_ACTIVE,
        is_visible=True,
    )

    # 2. Draft product in active category -> invisible
    Product.objects.create(
        name="Draft Serum",
        slug="draft-serum",
        sku="DFT-01",
        category=cat_active,
        price=Decimal("30.00"),
        stock_quantity=10,
        status=Product.STATUS_DRAFT,
        is_visible=True,
    )

    # 3. Hidden product in active category -> invisible
    Product.objects.create(
        name="Hidden Serum",
        slug="hidden-serum",
        sku="HID-01",
        category=cat_active,
        price=Decimal("50.00"),
        stock_quantity=5,
        status=Product.STATUS_ACTIVE,
        is_visible=False,
    )

    # 4. Active product in archived category -> invisible
    Product.objects.create(
        name="Old Toner",
        slug="old-toner",
        sku="TON-01",
        category=cat_archived,
        price=Decimal("20.00"),
        stock_quantity=15,
        status=Product.STATUS_ACTIVE,
        is_visible=True,
    )

    resp = api_client.get("/api/v1/storefront/products/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["count"] == 1
    assert data["results"][0]["slug"] == p1.slug
    assert data["results"][0]["effective_price"] == "45.00"
    assert data["results"][0]["is_in_stock"] is True

    # Detail view
    det_resp = api_client.get(f"/api/v1/storefront/products/{p1.slug}/")
    assert det_resp.status_code == status.HTTP_200_OK
    assert det_resp.json()["name"] == "Vitamin C Serum"

    # Detail view of hidden/draft product returns 404
    hidden_resp = api_client.get("/api/v1/storefront/products/draft-serum/")
    assert hidden_resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_backend_authoritative_price_and_stock_validation(product_admin_client):
    """Ensure backend validates prices, discounts, stock, and uniqueness."""
    cat = Category.objects.create(name="Creams", slug="creams", status=Category.STATUS_ACTIVE)

    # 1. Negative price rejected
    resp_neg_price = product_admin_client.post(
        "/api/v1/admin/products/",
        data={
            "name": "Invalid Price Cream",
            "slug": "invalid-price",
            "sku": "NEG-01",
            "category_id": cat.id,
            "price": "-10.00",
            "stock_quantity": 5,
        },
        format="json",
    )
    assert resp_neg_price.status_code == status.HTTP_400_BAD_REQUEST

    # 2. Negative stock rejected
    resp_neg_stock = product_admin_client.post(
        "/api/v1/admin/products/",
        data={
            "name": "Invalid Stock Cream",
            "slug": "invalid-stock",
            "sku": "NEG-02",
            "category_id": cat.id,
            "price": "30.00",
            "stock_quantity": -5,
        },
        format="json",
    )
    assert resp_neg_stock.status_code == status.HTTP_400_BAD_REQUEST

    # 3. Discount price >= regular price rejected
    resp_bad_disc = product_admin_client.post(
        "/api/v1/admin/products/",
        data={
            "name": "Bad Discount Cream",
            "slug": "bad-discount",
            "sku": "BAD-01",
            "category_id": cat.id,
            "price": "30.00",
            "discount_price": "35.00",
            "stock_quantity": 5,
        },
        format="json",
    )
    assert resp_bad_disc.status_code == status.HTTP_400_BAD_REQUEST

    # 4. Valid product with discount created and effective_price computed by backend
    resp_valid = product_admin_client.post(
        "/api/v1/admin/products/",
        data={
            "name": "Hydra Glow Cream",
            "slug": "hydra-glow-cream",
            "sku": "HGC-01",
            "category_id": cat.id,
            "price": "40.00",
            "discount_price": "32.00",
            "stock_quantity": 12,
            "status": "active",
            "is_visible": True,
            "images": [
                {"image_url": "https://images.unsplash.com/photo-1556228720-195a672e8a03", "is_primary": True}
            ],
        },
        format="json",
    )
    assert resp_valid.status_code == status.HTTP_201_CREATED
    data = resp_valid.json()
    assert data["price"] == "40.00"
    assert data["discount_price"] == "32.00"
    assert data["effective_price"] == "32.00"
    assert len(data["images"]) == 1
    assert data["images"][0]["is_primary"] is True

    # 5. Duplicate SKU rejected
    resp_dup_sku = product_admin_client.post(
        "/api/v1/admin/products/",
        data={
            "name": "Duplicate SKU Cream",
            "slug": "dup-sku-cream",
            "sku": "HGC-01",
            "category_id": cat.id,
            "price": "40.00",
            "stock_quantity": 5,
        },
        format="json",
    )
    assert resp_dup_sku.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_admin_product_rbac_and_archiving(api_client, readonly_staff_client, product_admin_client):
    cat = Category.objects.create(name="Masks", slug="masks", status=Category.STATUS_ACTIVE)
    p = Product.objects.create(
        name="Clay Mask",
        slug="clay-mask",
        sku="CM-01",
        category=cat,
        price=Decimal("18.00"),
        stock_quantity=15,
        status=Product.STATUS_ACTIVE,
    )

    # 1. Unauthenticated cannot access admin
    resp = api_client.get("/api/v1/admin/products/")
    assert resp.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    # 2. Readonly staff cannot update or delete
    patch_ro = readonly_staff_client.patch(
        f"/api/v1/admin/products/{p.id}/",
        data={"price": "22.00"},
        format="json",
    )
    assert patch_ro.status_code == status.HTTP_403_FORBIDDEN

    del_ro = readonly_staff_client.delete(f"/api/v1/admin/products/{p.id}/")
    assert del_ro.status_code == status.HTTP_403_FORBIDDEN

    # 3. Product admin can update and archive
    patch_admin = product_admin_client.patch(
        f"/api/v1/admin/products/{p.id}/",
        data={"price": "22.00"},
        format="json",
    )
    assert patch_admin.status_code == status.HTTP_200_OK
    assert patch_admin.json()["price"] == "22.00"

    # Soft archive via DELETE
    del_admin = product_admin_client.delete(f"/api/v1/admin/products/{p.id}/")
    assert del_admin.status_code == status.HTTP_204_NO_CONTENT
    p.refresh_from_db()
    assert p.status == Product.STATUS_ARCHIVED
