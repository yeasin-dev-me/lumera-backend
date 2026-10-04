"""Storefront Categories URLs."""
from django.urls import path
from .views import StorefrontCategoryDetailView, StorefrontCategoryListView

urlpatterns = [
    path("", StorefrontCategoryListView.as_view(), name="storefront-category-list"),
    path("<slug:slug>/", StorefrontCategoryDetailView.as_view(), name="storefront-category-detail"),
]
