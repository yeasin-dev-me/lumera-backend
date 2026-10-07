import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import Address, User
from apps.orders.models import Order, OrderItem, ReturnRequest, ReturnRequestItem


def address_payload(label, is_default=False):
    return {
        "label": label,
        "full_name": "Jane Doe",
        "phone": "01700000000",
        "address_line1": "1 Main Street",
        "city": "Dhaka",
        "is_default": is_default,
    }


@pytest.mark.django_db
def test_customer_can_patch_own_profile_but_not_email_or_staff():
    user = User.objects.create_user(email="profile@example.com", password="SecurePassword123!")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        "/api/v1/customer/me/",
        {"first_name": "Updated", "email": "attacker@example.com", "is_staff": True},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.first_name == "Updated"
    assert user.email == "profile@example.com"
    assert user.is_staff is False


@pytest.mark.django_db
def test_customer_addresses_keep_one_default_and_are_isolated():
    owner = User.objects.create_user(email="owner@example.com", password="SecurePassword123!")
    other = User.objects.create_user(email="other@example.com", password="SecurePassword123!")
    client = APIClient()
    client.force_authenticate(user=owner)

    first = client.post("/api/v1/customer/addresses/", address_payload("Home"), format="json")
    second = client.post(
        "/api/v1/customer/addresses/", address_payload("Office", True), format="json"
    )
    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_201_CREATED
    assert Address.objects.filter(user=owner, is_default=True).count() == 1

    client.force_authenticate(user=other)
    assert client.patch(
        f"/api/v1/customer/addresses/{first.json()['id']}/",
        {"label": "Stolen"},
        format="json",
    ).status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_admin_order_report_requires_dedicated_reports_permission():
    staff = User.objects.create_user(
        email="reporter@example.com", password="SecurePassword123!", is_staff=True
    )
    client = APIClient()
    client.force_authenticate(user=staff)
    assert client.get("/api/v1/admin/reports/orders/").status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_customer_returns_cannot_exceed_remaining_item_quantity_and_hide_staff_notes():
    user = User.objects.create_user(email="returns@example.com", password="testpass123!")
    order = Order.objects.create(
        order_number="RET-001",
        user=user,
        status=Order.STATUS_DELIVERED,
        subtotal="20.00",
        total="20.00",
        shipping_full_name="Jane Doe",
        shipping_phone="01700000000",
        shipping_address_line1="1 Main Street",
        shipping_city="Dhaka",
    )
    order_item = OrderItem.objects.create(
        order=order,
        product_name="Returnable item",
        product_sku="RET-001",
        unit_price="10.00",
        quantity=2,
        line_total="20.00",
    )
    previous_return = ReturnRequest.objects.create(
        order=order,
        user=user,
        reason="First return",
        status=ReturnRequest.STATUS_RECEIVED,
        staff_note="Internal warehouse note",
    )
    ReturnRequestItem.objects.create(
        return_request=previous_return,
        order_item=order_item,
        quantity=1,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/v1/customer/returns/",
        {
            "order_public_id": str(order.public_id),
            "reason": "Second return",
            "items": [{"order_item_id": order_item.id, "quantity": 2}],
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    detail = client.get(f"/api/v1/customer/returns/{previous_return.public_id}/")
    assert detail.status_code == status.HTTP_200_OK
    assert "staff_note" not in detail.json()
