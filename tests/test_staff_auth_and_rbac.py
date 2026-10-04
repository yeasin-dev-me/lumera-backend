import pytest
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import Role, User


@pytest.mark.django_db
def test_staff_login_and_non_staff_rejection():
    client = APIClient()

    # Regular customer
    User.objects.create_user(email="customer@example.com", password="Password123!", is_staff=False)
    # Staff user
    staff = User.objects.create_user(email="staff@example.com", password="StaffPassword123!", is_staff=True)
    role = Role.objects.create(name="catalog_editor", permissions=["products.read", "products.write"])
    staff.roles.add(role)

    # Customer rejected on CMS login with 403 Forbidden
    resp = client.post(
        "/api/v1/admin/auth/login/",
        data={"email": "customer@example.com", "password": "Password123!"},
        format="json",
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["error"]["code"] == "permission_denied"

    # Staff accepted on CMS login
    resp = client.post(
        "/api/v1/admin/auth/login/",
        data={"email": "staff@example.com", "password": "StaffPassword123!"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "access" in data
    assert "refresh" in data
    assert data["user"]["is_staff"] is True
    assert "products.read" in data["user"]["permissions"]
    assert "products.write" in data["user"]["permissions"]


@pytest.mark.django_db
def test_rbac_validation_hardening():
    # Valid permissions
    role = Role.objects.create(name="valid_role", permissions=["orders.read", "orders.update"])
    assert role.permissions == ["orders.read", "orders.update"]

    # Duplicates deduplicated
    role2 = Role.objects.create(name="dedup_role", permissions=["orders.read", "orders.read"])
    assert role2.permissions == ["orders.read"]

    # Non-list permissions rejected
    with pytest.raises(ValidationError):
        Role.objects.create(name="invalid_type", permissions="orders.read")

    with pytest.raises(ValidationError):
        Role.objects.create(name="invalid_dict", permissions={"perm": "orders.read"})

    # Malformed permission string formats rejected
    with pytest.raises(ValidationError):
        Role.objects.create(name="invalid_format1", permissions=["orders"])

    with pytest.raises(ValidationError):
        Role.objects.create(name="invalid_format2", permissions=["orders."])

    with pytest.raises(ValidationError):
        Role.objects.create(name="invalid_format3", permissions=[".read"])

    with pytest.raises(ValidationError):
        Role.objects.create(name="invalid_format4", permissions=["ORDERS.READ"])

    with pytest.raises(ValidationError):
        Role.objects.create(name="invalid_format5", permissions=[""])


@pytest.mark.django_db
def test_superuser_authorization_behavior():
    superuser = User.objects.create_superuser(
        email="superadmin@example.com",
        password="SuperPassword123!",
    )
    assert superuser.is_superuser is True
    assert superuser.is_staff is True
    assert superuser.has_perm_code("anything.arbitrary") is True
    assert superuser.get_permission_codes() == ["*"]


@pytest.mark.django_db
def test_rbac_view_level_enforcement():
    client = APIClient()

    # Staff without products.write
    viewer = User.objects.create_user(email="viewer@example.com", password="Password123!", is_staff=True)
    viewer_role = Role.objects.create(name="viewer", permissions=["products.read"])
    viewer.roles.add(viewer_role)

    # Staff with products.write
    editor = User.objects.create_user(email="editor@example.com", password="Password123!", is_staff=True)
    editor_role = Role.objects.create(name="editor", permissions=["products.write"])
    editor.roles.add(editor_role)

    # Viewer denied on /api/v1/admin/test-permission/
    client.force_authenticate(user=viewer)
    res = client.get("/api/v1/admin/test-permission/")
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert res.json()["error"]["code"] == "permission_denied"

    # Editor granted
    client.force_authenticate(user=editor)
    res = client.get("/api/v1/admin/test-permission/")
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["permission"] == "products.write"
