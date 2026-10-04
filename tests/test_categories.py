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
def staff_client():
    client = APIClient()
    user = User.objects.create_user(
        email="category_admin@example.com",
        password="StaffPassword123!",
        is_staff=True,
    )
    role = Role.objects.create(
        name="category_manager",
        permissions=["categories.read", "categories.write", "categories.delete"],
    )
    user.roles.add(role)
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def readonly_staff_client():
    client = APIClient()
    user = User.objects.create_user(
        email="readonly_staff@example.com",
        password="StaffPassword123!",
        is_staff=True,
    )
    role = Role.objects.create(
        name="category_viewer",
        permissions=["categories.read"],
    )
    user.roles.add(role)
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_storefront_category_listing_and_visibility(api_client):
    # Setup categories: active, draft, archived
    Category.objects.create(name="Active Skincare", slug="skincare", status=Category.STATUS_ACTIVE, sort_order=1)
    Category.objects.create(name="Active Serums", slug="serums", status=Category.STATUS_ACTIVE, sort_order=0)
    Category.objects.create(name="Draft Suncare", slug="suncare", status=Category.STATUS_DRAFT)
    Category.objects.create(name="Archived Toners", slug="toners", status=Category.STATUS_ARCHIVED)

    # Storefront list should return only active categories, ordered by sort_order
    resp = api_client.get("/api/v1/storefront/categories/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 2
    assert data[0]["slug"] == "serums"
    assert data[1]["slug"] == "skincare"

    # Storefront detail
    resp_active = api_client.get("/api/v1/storefront/categories/serums/")
    assert resp_active.status_code == status.HTTP_200_OK
    assert resp_active.json()["name"] == "Active Serums"

    resp_draft = api_client.get("/api/v1/storefront/categories/suncare/")
    assert resp_draft.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_admin_category_crud_and_permissions(api_client, readonly_staff_client, staff_client):
    # 1. Unauthenticated access rejected
    unauth_resp = api_client.get("/api/v1/admin/categories/")
    assert unauth_resp.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    # 2. Readonly staff can list
    ro_resp = readonly_staff_client.get("/api/v1/admin/categories/")
    assert ro_resp.status_code == status.HTTP_200_OK

    # 3. Readonly staff cannot create
    ro_create = readonly_staff_client.post(
        "/api/v1/admin/categories/",
        data={"name": "Moisturizers", "slug": "moisturizers"},
        format="json",
    )
    assert ro_create.status_code == status.HTTP_403_FORBIDDEN

    # 4. Authorized staff can create
    create_resp = staff_client.post(
        "/api/v1/admin/categories/",
        data={
            "name": "Moisturizers",
            "slug": "moisturizers",
            "description": "Hydrating moisturizers",
            "status": "active",
            "sort_order": 5,
        },
        format="json",
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    cat_id = create_resp.json()["id"]

    # 5. Duplicate slug rejected
    dup_resp = staff_client.post(
        "/api/v1/admin/categories/",
        data={"name": "Duplicate Moisturizers", "slug": "moisturizers"},
        format="json",
    )
    assert dup_resp.status_code == status.HTTP_400_BAD_REQUEST

    # 6. Update category
    patch_resp = staff_client.patch(
        f"/api/v1/admin/categories/{cat_id}/",
        data={"description": "Updated hydrating moisturizers"},
        format="json",
    )
    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.json()["description"] == "Updated hydrating moisturizers"


@pytest.mark.django_db
def test_category_archive_conflict_with_active_products(staff_client):
    cat = Category.objects.create(name="Cleansers", slug="cleansers", status=Category.STATUS_ACTIVE)
    # Create active product in this category
    Product.objects.create(
        name="Gentle Cleanser",
        slug="gentle-cleanser",
        sku="GC-001",
        category=cat,
        price="25.00",
        stock_quantity=10,
        status=Product.STATUS_ACTIVE,
    )

    # Attempt to delete/archive category should fail with 409 Conflict (BR-05)
    del_resp = staff_client.delete(f"/api/v1/admin/categories/{cat.id}/")
    assert del_resp.status_code == status.HTTP_409_CONFLICT
    assert del_resp.json()["error"]["code"] == "conflict"
    cat.refresh_from_db()
    assert cat.status == Category.STATUS_ACTIVE

    # Archive or deactivate product first
    prod = cat.products.first()
    prod.status = Product.STATUS_ARCHIVED
    prod.save()

    # Now archive should succeed (status becomes archived)
    del_resp2 = staff_client.delete(f"/api/v1/admin/categories/{cat.id}/")
    assert del_resp2.status_code == status.HTTP_204_NO_CONTENT
    cat.refresh_from_db()
    assert cat.status == Category.STATUS_ARCHIVED
