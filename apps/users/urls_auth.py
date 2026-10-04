"""Storefront Customer Auth URLs."""
from django.urls import path
from .views import CustomerLoginView, LumeraTokenRefreshView

app_name = "auth"

urlpatterns = [
    path("login/", CustomerLoginView.as_view(), name="customer-login"),
    path("refresh/", LumeraTokenRefreshView.as_view(), name="customer-refresh"),
]
