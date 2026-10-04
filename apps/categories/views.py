"""Views for Categories domain."""
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from apps.users.permissions import HasPermission
from .models import Category
from .serializers import CategorySerializer


# --- Storefront Views ---

class StorefrontCategoryListView(generics.ListAPIView):
    """List all active categories for the customer storefront."""

    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(status=Category.STATUS_ACTIVE).order_order() if hasattr(Category.objects, "order_order") else Category.objects.filter(status=Category.STATUS_ACTIVE).order_by("sort_order", "name")


class StorefrontCategoryDetailView(generics.RetrieveAPIView):
    """Retrieve details for a single active category by slug."""

    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Category.objects.filter(status=Category.STATUS_ACTIVE)


# --- CMS Admin Views ---

class AdminCategoryListCreateView(generics.ListCreateAPIView):
    """List and create categories in CMS."""

    serializer_class = CategorySerializer
    pagination_class = None

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasPermission("categories.write")()]
        return [HasPermission("categories.read")()]

    def get_queryset(self):
        return Category.objects.all().order_by("sort_order", "name")


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or archive/delete a category in CMS."""

    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [HasPermission("categories.delete")()]
        if self.request.method in ["PUT", "PATCH"]:
            return [HasPermission("categories.write")()]
        return [HasPermission("categories.read")()]

    def get_object(self):
        identifier = self.kwargs.get("id")
        queryset = Category.objects.all()
        if str(identifier).isdigit():
            return get_object_or_404(queryset, pk=int(identifier))
        return get_object_or_404(queryset, slug=identifier)

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        # BR-05: A category containing active products cannot be archived without reassigning them.
        if category.has_active_products():
            return Response(
                {
                    "error": {
                        "code": "conflict",
                        "message": "Cannot archive category containing active products. Reassign active products first.",
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Soft archive
        category.status = Category.STATUS_ARCHIVED
        category.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
