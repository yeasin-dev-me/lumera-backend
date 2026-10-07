"""Customer routing for communication preferences and notification history."""
from django.urls import path
from .views_customer import (
    CustomerCommunicationPreferenceView,
    CustomerNotificationListView,
)

urlpatterns = [
    path("communication-preferences/", CustomerCommunicationPreferenceView.as_view(), name="customer-communication-preferences"),
    path("notifications/", CustomerNotificationListView.as_view(), name="customer-notifications"),
]
