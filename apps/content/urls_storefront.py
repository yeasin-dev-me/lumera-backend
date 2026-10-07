"""Storefront URLs for content."""
from django.urls import path
from .views_storefront import (
    StorefrontBannersView,
    StorefrontContentDetailView,
    StorefrontHomeContentView,
)


urlpatterns = [
    path("home/", StorefrontHomeContentView.as_view(), name="content-home"),
    path("banners/", StorefrontBannersView.as_view(), name="content-banners"),
    path("<slug:slug>/", StorefrontContentDetailView.as_view(), name="content-detail"),
]
