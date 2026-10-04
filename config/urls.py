"""Root URL Configuration for Lumera Backend.

Architecture rules:
- Django Admin ('django.contrib.admin') is explicitly NOT routed.
- Base path: /api/v1/
- Namespaces:
    /api/v1/health/      -> Liveness/readiness health check
    /api/v1/auth/        -> Storefront customer authentication
    /api/v1/storefront/  -> Public storefront endpoints
    /api/v1/customer/    -> Authenticated customer private endpoints
    /api/v1/admin/       -> CMS admin operations (staff only)
    /api/v1/internal/    -> Machine callers & webhook endpoints
"""

from django.urls import include, path, re_path
from apps.common.views import custom_404_view, custom_500_view, health_check

urlpatterns = [
    # System / Health
    path("api/v1/health/", health_check, name="health-check"),

    # Namespaces
    path("api/v1/auth/", include("apps.users.urls_auth")),
    path("api/v1/storefront/", include("apps.common.urls_storefront")),
    path("api/v1/customer/", include("apps.users.urls_customer")),
    path("api/v1/admin/", include("apps.users.urls_admin")),
    path("api/v1/internal/", include("apps.common.urls_internal")),

    # Catch-all for undefined /api/v1/ endpoints to ensure standard JSON 404 response
    re_path(r"^api/v1/.*$", custom_404_view, name="api-v1-404-fallback"),
]

# Standard JSON error handlers
handler404 = "apps.common.views.custom_404_view"
handler500 = "apps.common.views.custom_500_view"
