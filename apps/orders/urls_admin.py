"""Staff admin URLs for Orders in CMS."""
from django.urls import path
from .views_admin import AdminOrderDetailView, AdminOrderListView

urlpatterns = [
    path("orders/", AdminOrderListView.as_view(), name="admin-orders-list"),
    path("orders/<uuid:public_id>/", AdminOrderDetailView.as_view(), name="admin-order-detail"),
]
