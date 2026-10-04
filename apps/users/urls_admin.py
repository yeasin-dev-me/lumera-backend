"""CMS Admin API URLs."""
from django.urls import path
from .views import (
    AdminMeView,
    AdminTestPermissionView,
    CMSLoginView,
    CMSLogoutView,
    LumeraTokenRefreshView,
)

app_name = "admin"

urlpatterns = [
    path("auth/login/", CMSLoginView.as_view(), name="admin-login"),
    path("auth/refresh/", LumeraTokenRefreshView.as_view(), name="admin-refresh"),
    path("auth/logout/", CMSLogoutView.as_view(), name="admin-logout"),
    path("auth/me/", AdminMeView.as_view(), name="admin-me"),
    path("test-permission/", AdminTestPermissionView.as_view(), name="admin-test-permission"),
]
