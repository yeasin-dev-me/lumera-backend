"""Customer Private API URLs."""
from django.urls import path
from .views import CustomerMeView

app_name = "customer"

urlpatterns = [
    path("me/", CustomerMeView.as_view(), name="customer-me"),
]
