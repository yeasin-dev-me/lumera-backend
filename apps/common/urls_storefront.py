from django.conf import settings
from django.http import JsonResponse
from django.urls import path

app_name = "storefront"


def config_view(request):
    """Returns safe public storefront config."""
    return JsonResponse(
        {
            "site_name": "Lumera",
            "currency": "USD",
            "version": "v1",
            "announcement_text": getattr(
                settings,
                "LUMERA_ANNOUNCEMENT_TEXT",
                "Complimentary shipping on wholesale orders over $150",
            ),
            "meta_pixel_id": getattr(settings, "META_PIXEL_ID", ""),
            "ga4_measurement_id": getattr(settings, "GA4_MEASUREMENT_ID", ""),
            "default_seo_title": "Lumera | Modern Skincare & Pure Beauty",
            "default_seo_description": "Experience modern, thoughtful skincare engineered for radiance and purity.",
        }
    )


urlpatterns = [
    path("config/", config_view, name="storefront-config"),
]
