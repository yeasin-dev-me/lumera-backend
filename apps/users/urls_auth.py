"""Storefront Customer Auth URLs."""
from django.urls import path
from .views import (
    CustomerLoginView,
    CustomerLogoutView,
    CustomerRegistrationView,
    LumeraTokenRefreshView,
)

app_name = "auth"

urlpatterns = [
    path("register/", CustomerRegistrationView.as_view(), name="customer-register"),
    path("login/", CustomerLoginView.as_view(), name="customer-login"),
    path("refresh/", LumeraTokenRefreshView.as_view(), name="customer-refresh"),
    path("logout/", CustomerLogoutView.as_view(), name="customer-logout"),
]
