"""Category domain models for Lumera."""
from django.db import models
from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    """Product Category model (flat structure per ADR-0004 & database spec)."""

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
    description = models.TextField(blank=True, default="")
    image_url = models.CharField(max_length=500, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    sort_order = models.IntegerField(default=0)
    seo_title = models.CharField(max_length=255, blank=True, default="")
    seo_description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "categories_category"
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def has_active_products(self) -> bool:
        """Check if category has active products."""
        return self.products.filter(status="active").exists()
