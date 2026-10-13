"""Views for Products domain."""
import uuid
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from apps.categories.models import Category
from apps.common.pagination import StandardResultsSetPagination
from apps.users.permissions import HasPermission
from .models import Product
from .serializers import (
    ProductCreateUpdateSerializer,
    ProductDetailSerializer,
    ProductListItemSerializer,
)


# --- Storefront Views ---

class StorefrontProductListView(generics.ListAPIView):
    """List active and visible products belonging to active categories (BR-04)."""

    permission_classes = [AllowAny]
    serializer_class = ProductListItemSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = (
            Product.objects.filter(
                status=Product.STATUS_ACTIVE,
                is_visible=True,
                category__status=Category.STATUS_ACTIVE,
            )
            .select_related("category")
            .prefetch_related("images")
        )

        category_slug = self.request.query_params.get("category")
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        search_query = self.request.query_params.get("search") or self.request.query_params.get("q")
        if search_query:
            search_query = search_query.strip()
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(sku__icontains=search_query)
            )

        ordering = self.request.query_params.get("ordering")
        allowed_orderings = {
            "price": "price",
            "-price": "-price",
            "created_at": "created_at",
            "-created_at": "-created_at",
            "name": "name",
            "-name": "-name",
            "sort_order": "sort_order",
        }
        if ordering in allowed_orderings:
            queryset = queryset.order_by(allowed_orderings[ordering])
        else:
            queryset = queryset.order_by("sort_order", "-created_at")

        return queryset


class StorefrontProductDetailView(generics.RetrieveAPIView):
    """Retrieve details for a single active and visible product by slug or public_id (BR-04)."""

    permission_classes = [AllowAny]
    serializer_class = ProductDetailSerializer

    def get_queryset(self):
        return (
            Product.objects.filter(
                status=Product.STATUS_ACTIVE,
                is_visible=True,
                category__status=Category.STATUS_ACTIVE,
            )
            .select_related("category")
            .prefetch_related("images")
        )

    def get_object(self):
        slug_or_id = self.kwargs.get("slug")
        queryset = self.get_queryset()
        try:
            val_uuid = uuid.UUID(str(slug_or_id))
            obj = queryset.filter(public_id=val_uuid).first()
            if obj:
                return obj
        except (ValueError, TypeError):
            pass
        return get_object_or_404(queryset, slug=slug_or_id)


# --- CMS Admin Views ---

class AdminProductListCreateView(generics.ListCreateAPIView):
    """List and create products for CMS management."""

    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasPermission("products.write")()]
        return [HasPermission("products.read")()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer

    def get_queryset(self):
        queryset = Product.objects.all().select_related("category").prefetch_related("images")

        category_id = self.request.query_params.get("category_id")
        if category_id and category_id.isdigit():
            queryset = queryset.filter(category_id=int(category_id))

        status_param = self.request.query_params.get("status")
        if status_param in [Product.STATUS_DRAFT, Product.STATUS_ACTIVE, Product.STATUS_ARCHIVED]:
            queryset = queryset.filter(status=status_param)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(sku__icontains=search) | Q(slug__icontains=search)
            )

        return queryset.order_by("sort_order", "-created_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        response_serializer = ProductDetailSerializer(product)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class AdminProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or archive/delete a product in CMS."""

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [HasPermission("products.delete")()]
        if self.request.method in ["PUT", "PATCH"]:
            return [HasPermission("products.write")()]
        return [HasPermission("products.read")()]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer

    def get_object(self):
        identifier = self.kwargs.get("id")
        queryset = Product.objects.all().select_related("category").prefetch_related("images")

        if str(identifier).isdigit():
            return get_object_or_404(queryset, pk=int(identifier))

        # Check for UUID public_id
        try:
            uuid_val = uuid.UUID(str(identifier))
            return get_object_or_404(queryset, public_id=uuid_val)
        except ValueError:
            pass

        return get_object_or_404(queryset, slug=identifier)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        response_serializer = ProductDetailSerializer(product)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        # Soft archive per specification / BR-05
        product.status = Product.STATUS_ARCHIVED
        product.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
