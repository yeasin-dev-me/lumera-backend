import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User


@pytest.mark.django_db
def test_customer_registration_success():
    client = APIClient()
    payload = {
        "email": "newcustomer@example.com",
        "password": "ValidPassword2026!",
        "first_name": "Alice",
        "last_name": "Smith",
        "phone": "+123456789",
    }
    response = client.post("/api/v1/auth/register/", data=payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "access" in data
    assert "refresh" in data
    assert "user" in data
    assert data["user"]["email"] == "newcustomer@example.com"
    assert data["user"]["first_name"] == "Alice"
    assert data["user"]["is_staff"] is False
    assert "password" not in data["user"]

    # Verify user exists in database and is active
    user = User.objects.get(email="newcustomer@example.com")
    assert user.is_active is True
    assert user.is_staff is False


@pytest.mark.django_db
def test_customer_registration_validation_rules():
    client = APIClient()

    # Short password (< 10 chars)
    payload = {
        "email": "invalid@example.com",
        "password": "short",
    }
    response = client.post("/api/v1/auth/register/", data=payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["code"] == "validation_error"

    # Duplicate email
    User.objects.create_user(email="existing@example.com", password="Password123!")
    payload = {
        "email": "EXISTING@example.com",
        "password": "ValidPassword2026!",
    }
    response = client.post("/api/v1/auth/register/", data=payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.json()["error"]["details"]


@pytest.mark.django_db
def test_customer_login_flow():
    client = APIClient()
    user = User.objects.create_user(email="buyer@example.com", password="SecurePassword123!")

    # Valid login
    response = client.post(
        "/api/v1/auth/login/",
        data={"email": "buyer@example.com", "password": "SecurePassword123!"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access" in data
    assert "refresh" in data
    access_token = data["access"]

    # Authenticated access to customer profile
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    me_resp = client.get("/api/v1/customer/me/")
    assert me_resp.status_code == status.HTTP_200_OK
    assert me_resp.json()["email"] == "buyer@example.com"

    # Invalid password
    client.credentials()  # clear credentials
    bad_resp = client.post(
        "/api/v1/auth/login/",
        data={"email": "buyer@example.com", "password": "WrongPassword"},
        format="json",
    )
    assert bad_resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert bad_resp.json()["error"]["code"] in ["authentication_failed", "token_not_valid", "invalid_credentials"]


@pytest.mark.django_db
def test_inactive_customer_cannot_login():
    client = APIClient()
    User.objects.create_user(email="inactive@example.com", password="Password123!", is_active=False)

    response = client.post(
        "/api/v1/auth/login/",
        data={"email": "inactive@example.com", "password": "Password123!"},
        format="json",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
