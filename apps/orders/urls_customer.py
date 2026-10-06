"""Customer URLs for Checkout and Orders."""
from django.urls import path
from .views_customer import (
    CheckoutPreviewView,
    CustomerOrderCancelView,
    CustomerOrderDetailView,
    CustomerOrderListView,
    CustomerOrderTimelineView,
)

urlpatterns = [
    path("checkout/", CheckoutPreviewView.as_view(), name="customer-checkout-preview"),
    path("orders/", CustomerOrderListView.as_view(), name="customer-orders-list-create"),
    path("orders/<uuid:public_id>/", CustomerOrderDetailView.as_view(), name="customer-order-detail"),
    path("orders/<uuid:public_id>/cancel/", CustomerOrderCancelView.as_view(), name="customer-order-cancel"),
    path("orders/<uuid:public_id>/timeline/", CustomerOrderTimelineView.as_view(), name="customer-order-timeline"),
]

