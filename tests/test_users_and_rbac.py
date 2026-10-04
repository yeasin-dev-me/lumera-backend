import uuid
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import Role, User


@pytest.mark.django_db
def test_user_creation_and_public_id():
    user = User.objects.create_user(
        email="customer@example.com",
        password="SecurePassword123!",
        first_name="Jane",
        last_name="Doe",
    )
    assert user.email == "customer@example.com"
    assert isinstance(user.public_id, uuid.UUID)
    assert user.is_active is True
    assert user.is_staff is False
    assert user.check_password("SecurePassword123!") is True


@pytest.mark.django_db
def test_role_and_permission_system():
    user = User.objects.create_user(
        email="staff@example.com",
        password="StaffPassword123!",
        is_staff=True,
    )
    order_role = Role.objects.create(
        name="order_manager",
        description="Can view and update orders",
        permissions=["orders.read", "orders.update"],
    )
    user.roles.add(order_role)

    assert user.has_perm_code("orders.read") is True
    assert user.has_perm_code("orders.update") is True
    assert user.has_perm_code("products.write") is False
    assert "orders.read" in user.get_permission_codes()


@pytest.mark.django_db
def test_admin_me_endpoint_requires_staff():
    client = APIClient()
    regular_user = User.objects.create_user(
        email="user@example.com",
        password="Password123!",
        is_staff=False,
    )
    staff_user = User.objects.create_user(
        email="admin@example.com",
        password="AdminPassword123!",
        is_staff=True,
    )

    # Customer user denied on /api/v1/admin/auth/me/
    client.force_authenticate(user=regular_user)
    response = client.get("/api/v1/admin/auth/me/")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Staff user allowed
    client.force_authenticate(user=staff_user)
    response = client.get("/api/v1/admin/auth/me/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "admin@example.com"
    assert data["is_staff"] is True
    assert "permissions" in data
