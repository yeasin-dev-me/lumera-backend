"""Storefront Products URLs."""
from django.urls import path
from .views import StorefrontProductDetailView, StorefrontProductListView

urlpatterns = [
    path("", StorefrontProductListView.as_view(), name="storefront-product-list"),
    path("<slug:slug>/", StorefrontProductDetailView.as_view(), name="storefront-product-detail"),
]
