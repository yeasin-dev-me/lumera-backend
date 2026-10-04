import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User


@pytest.mark.django_db
def test_jwt_refresh_and_rotation_lifecycle():
    client = APIClient()
    user = User.objects.create_user(email="lifecycle@example.com", password="Password123!")

    # Login to obtain initial tokens
    login_resp = client.post(
        "/api/v1/auth/login/",
        data={"email": "lifecycle@example.com", "password": "Password123!"},
        format="json",
    )
    assert login_resp.status_code == status.HTTP_200_OK
    initial_refresh = login_resp.json()["refresh"]

    # First refresh: succeeds and rotates
    refresh_resp = client.post(
        "/api/v1/auth/refresh/",
        data={"refresh": initial_refresh},
        format="json",
    )
    assert refresh_resp.status_code == status.HTTP_200_OK
    data = refresh_resp.json()
    assert "access" in data
    assert "refresh" in data
    second_refresh = data["refresh"]

    # Reused initial refresh token MUST be rejected (blacklisted after rotation)
    reused_resp = client.post(
        "/api/v1/auth/refresh/",
        data={"refresh": initial_refresh},
        format="json",
    )
    assert reused_resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert reused_resp.json()["error"]["code"] in ["token_not_valid", "authentication_failed"]

    # Second refresh token works
    third_refresh_resp = client.post(
        "/api/v1/auth/refresh/",
        data={"refresh": second_refresh},
        format="json",
    )
    assert third_refresh_resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_invalid_and_tampered_token_rejection():
    client = APIClient()

    # Tampered refresh token
    bad_resp = client.post(
        "/api/v1/auth/refresh/",
        data={"refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.token"},
        format="json",
    )
    assert bad_resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Empty refresh token
    empty_resp = client.post(
        "/api/v1/auth/refresh/",
        data={"refresh": ""},
        format="json",
    )
    assert empty_resp.status_code == status.HTTP_400_BAD_REQUEST or empty_resp.status_code == status.HTTP_401_UNAUTHORIZED
