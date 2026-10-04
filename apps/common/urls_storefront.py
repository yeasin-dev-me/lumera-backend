"""Public Storefront API URLs."""
from django.http import JsonResponse
from django.urls import path

app_name = "storefront"


def config_view(request):
    """Returns safe public storefront config."""
    return JsonResponse({"site_name": "Lumera", "currency": "USD", "version": "v1"})


urlpatterns = [
    path("config/", config_view, name="storefront-config"),
]
