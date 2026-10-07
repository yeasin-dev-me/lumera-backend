"""Customer Private API URLs."""
from django.urls import path
from .views import CustomerAddressDetailView, CustomerAddressListView, CustomerMeView

app_name = "customer"

urlpatterns = [
    path("me/", CustomerMeView.as_view(), name="customer-me"),
    path("addresses/", CustomerAddressListView.as_view(), name="customer-addresses"),
    path("addresses/<uuid:public_id>/", CustomerAddressDetailView.as_view(), name="customer-address"),
]
