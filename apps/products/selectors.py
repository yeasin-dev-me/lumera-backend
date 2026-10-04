"""Read-side helpers for Products shared with other apps (ADR-0002: cross-app calls go
through services/selectors, not views)."""
from django.db.models import QuerySet
from apps.categories.models import Category
from .models import Product


def storefront_eligible_products() -> QuerySet[Product]:
    """Products a customer may see and newly add to cart/wishlist (BR-04)."""
    return Product.objects.filter(
        status=Product.STATUS_ACTIVE,
        is_visible=True,
        category__status=Category.STATUS_ACTIVE,
    )


def is_storefront_eligible(product: Product) -> bool:
    """In-memory BR-04 check for an already-loaded product (select_related('category'))."""
    return (
        product.status == Product.STATUS_ACTIVE
        and product.is_visible
        and product.category.status == Category.STATUS_ACTIVE
    )


def primary_image_url(product: Product) -> str | None:
    """Primary (or first) image URL using prefetched images when available.

    Mirrors ``Product.primary_image`` but avoids one query per product when
    ``prefetch_related('images')`` was used (ProductImage default ordering puts the
    primary image first).
    """
    images = list(product.images.all())
    return images[0].image_url if images else None
