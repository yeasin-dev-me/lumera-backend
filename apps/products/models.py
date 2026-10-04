"""Product and ProductImage domain models for Lumera."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from apps.common.models import PublicIdModel, TimeStampedModel


class Product(PublicIdModel, TimeStampedModel):
    """Authoritative product model for catalog, pricing, and stock."""

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, default="")
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.PROTECT,
        related_name="products",
    )
    price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    stock_quantity = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    is_visible = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    seo_title = models.CharField(max_length=255, blank=True, default="")
    seo_description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "products_product"
        ordering = ["sort_order", "-created_at"]
        constraints = [
            models.CheckConstraint(
                check=Q(price__gte=0),
                name="check_product_price_non_negative",
            ),
            models.CheckConstraint(
                check=Q(stock_quantity__gte=0),
                name="check_product_stock_quantity_non_negative",
            ),
            models.CheckConstraint(
                check=(
                    Q(discount_price__isnull=True)
                    | (Q(discount_price__gte=0) & Q(discount_price__lt=F("price")))
                ),
                name="check_product_discount_price_valid",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def clean(self):
        super().clean()
        if self.price is not None and self.price < Decimal("0.00"):
            raise ValidationError({"price": "Price cannot be negative."})
        if self.stock_quantity is not None and self.stock_quantity < 0:
            raise ValidationError({"stock_quantity": "Stock quantity cannot be negative."})
        if self.discount_price is not None:
            if self.discount_price < Decimal("0.00"):
                raise ValidationError({"discount_price": "Discount price cannot be negative."})
            if self.price is not None and self.discount_price >= self.price:
                raise ValidationError({"discount_price": "Discount price must be less than regular price."})

    @property
    def effective_price(self) -> Decimal:
        """Calculate authoritative effective price (BR-02a)."""
        if self.discount_price is not None and self.discount_price > Decimal("0.00"):
            return self.discount_price
        return self.price

    @property
    def is_in_stock(self) -> bool:
        """Stock availability check."""
        return self.stock_quantity > 0

    @property
    def primary_image(self) -> str | None:
        """Return image_url of primary image or first available image."""
        img = self.images.filter(is_primary=True).first() or self.images.first()
        return img.image_url if img else None


class ProductImage(TimeStampedModel):
    """Product gallery image with ordering and primary badge."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image_url = models.CharField(max_length=500)
    alt_text = models.CharField(max_length=255, blank=True, default="")
    sort_order = models.IntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "products_productimage"
        ordering = ["-is_primary", "sort_order", "id"]

    def __str__(self):
        return f"Image for {self.product.name} ({'Primary' if self.is_primary else 'Gallery'})"
