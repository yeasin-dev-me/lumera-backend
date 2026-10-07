from django.urls import path
from .views_admin import AdminRefundView

urlpatterns = [
    path("refunds/", AdminRefundView.as_view(), name="admin-refunds"),
]
