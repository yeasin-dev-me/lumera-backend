"""Staff CMS routing for operational notification visibility and retry actions."""
from django.urls import path
from .views_admin import (
    AdminNotificationListView,
    AdminNotificationDetailView,
    AdminNotificationResendView,
)

urlpatterns = [
    path("notifications/", AdminNotificationListView.as_view(), name="admin-notifications-list"),
    path("notifications/<uuid:public_id>/", AdminNotificationDetailView.as_view(), name="admin-notifications-detail"),
    path("notifications/<uuid:public_id>/resend/", AdminNotificationResendView.as_view(), name="admin-notifications-resend"),
]
