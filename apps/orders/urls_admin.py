"""Staff admin URLs for Orders in CMS."""
from django.urls import path
from .views_admin import (
    AdminOrderDetailView,
    AdminOrderFulfillmentView,
    AdminOrderListView,
    AdminOrderReportView,
    AdminOrderTransitionView,
    AdminReturnDetailView,
    AdminReturnListView,
    AdminReturnTransitionView,
)

urlpatterns = [
    path("reports/orders/", AdminOrderReportView.as_view(), name="admin-order-report"),
    path("returns/", AdminReturnListView.as_view(), name="admin-returns-list"),
    path("returns/<uuid:public_id>/", AdminReturnDetailView.as_view(), name="admin-return-detail"),
    path("returns/<uuid:public_id>/<str:action>/", AdminReturnTransitionView.as_view(), name="admin-return-transition"),
    path("orders/", AdminOrderListView.as_view(), name="admin-orders-list"),
    path("orders/<uuid:public_id>/", AdminOrderDetailView.as_view(), name="admin-order-detail"),
    path("orders/<uuid:public_id>/transition/", AdminOrderTransitionView.as_view(), name="admin-order-transition"),
    path("orders/<uuid:public_id>/fulfillment/", AdminOrderFulfillmentView.as_view(), name="admin-order-fulfillment"),
]
