"""Internal machine URLs for Payments domain (ADR-0008, ADR-0014)."""
from django.urls import path
from .views_webhook import PaymentWebhookView

urlpatterns = [
    path("payments/webhook/<str:gateway>/", PaymentWebhookView.as_view(), name="internal-payment-webhook"),
]
