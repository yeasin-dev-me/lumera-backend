"""Internal Service & Webhook URLs."""
from django.http import JsonResponse
from django.urls import path

app_name = "internal"


def internal_ping(request):
    return JsonResponse({"status": "internal_ok"})


urlpatterns = [
    path("ping/", internal_ping, name="internal-ping"),
]
