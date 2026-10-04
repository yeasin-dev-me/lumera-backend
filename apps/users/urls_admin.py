"""CMS Admin API URLs."""
from django.urls import path
from .views import AdminMeView, CMSLoginView, LumeraTokenRefreshView

app_name = "admin"

urlpatterns = [
    path("auth/login/", CMSLoginView.as_view(), name="admin-login"),
    path("auth/refresh/", LumeraTokenRefreshView.as_view(), name="admin-refresh"),
    path("auth/me/", AdminMeView.as_view(), name="admin-me"),
]
