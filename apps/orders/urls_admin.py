"""Staff admin URLs for Orders in CMS."""
from django.urls import path
from .views_admin import (
    AdminOrderDetailView,
    AdminOrderFulfillmentView,
    AdminOrderListView,
    AdminOrderTransitionView,
)

urlpatterns = [
    path("orders/", AdminOrderListView.as_view(), name="admin-orders-list"),
    path("orders/<uuid:public_id>/", AdminOrderDetailView.as_view(), name="admin-order-detail"),
    path("orders/<uuid:public_id>/transition/", AdminOrderTransitionView.as_view(), name="admin-order-transition"),
    path("orders/<uuid:public_id>/fulfillment/", AdminOrderFulfillmentView.as_view(), name="admin-order-fulfillment"),
]

