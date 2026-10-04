import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_unauthenticated_protected_endpoint():
    client = APIClient()
    response = client.get("/api/v1/customer/me/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "not_authenticated"


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_not_found_endpoint():
    client = APIClient()
    response = client.get("/api/v1/non-existent-endpoint/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers.get("Content-Type") == "application/json"
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "not_found"
