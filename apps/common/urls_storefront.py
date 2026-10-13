from django.conf import settings
from django.http import JsonResponse
from django.urls import path

app_name = "storefront"


def config_view(request):
    """Returns safe public storefront config."""
    return JsonResponse(
        {
            "site_name": "Penguin Mart",
            "currency": "USD",
            "version": "v1",
            "announcement_text": getattr(
                settings,
                "LUMERA_ANNOUNCEMENT_TEXT",
                "Complimentary shipping on orders over $75 · Welcome to Penguin Mart",
            ),
            "meta_pixel_id": getattr(settings, "META_PIXEL_ID", ""),
            "ga4_measurement_id": getattr(settings, "GA4_MEASUREMENT_ID", ""),
            "default_seo_title": "Penguin Mart | Skin Care & Beauty",
            "default_seo_description": "Penguin Mart — Pure, thoughtful skincare & beauty engineered for radiance and purity.",
        }
    )


urlpatterns = [
    path("config/", config_view, name="storefront-config"),
]
