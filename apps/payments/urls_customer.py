"""Customer URLs for Payments domain (ADR-0014)."""
from django.urls import path
from .views_customer import CustomerOrderPaymentView

urlpatterns = [
    path("orders/<uuid:public_id>/payment/", CustomerOrderPaymentView.as_view(), name="customer-order-payment"),
]
