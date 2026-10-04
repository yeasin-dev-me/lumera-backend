"""Admin Products URLs."""
from django.urls import path
from .views import AdminProductDetailView, AdminProductListCreateView

urlpatterns = [
    path("", AdminProductListCreateView.as_view(), name="admin-product-list-create"),
    path("<str:id>/", AdminProductDetailView.as_view(), name="admin-product-detail"),
]
