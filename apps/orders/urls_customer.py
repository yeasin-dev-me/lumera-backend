"""Customer URLs for Checkout and Orders."""
from django.urls import path
from .views_customer import (
    CheckoutPreviewView,
    CustomerOrderDetailView,
    CustomerOrderListView,
)

urlpatterns = [
    path("checkout/", CheckoutPreviewView.as_view(), name="customer-checkout-preview"),
    path("orders/", CustomerOrderListView.as_view(), name="customer-orders-list-create"),
    path("orders/<uuid:public_id>/", CustomerOrderDetailView.as_view(), name="customer-order-detail"),
]
