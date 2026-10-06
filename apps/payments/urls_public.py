"""Public / Provider URLs for Payments domain (ADR-0014)."""
from django.urls import path
from .views_webhook import PaymentWebhookView

urlpatterns = [
    path("webhook/<str:gateway>/", PaymentWebhookView.as_view(), name="payment-webhook"),
    path("callback/<str:gateway>/", PaymentWebhookView.as_view(), name="payment-callback"),
]
