"""Content and Campaign domain models for Lumera."""
import re
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from apps.common.models import PublicIdModel, TimeStampedModel

SCRIPT_TAG_REGEX = re.compile(r"<\s*script[^>]*>", re.IGNORECASE)


def sanitize_plain_text(value: str) -> str:
    """Sanitize text input to ensure no embedded executable script tags exist."""
    if not value:
        return value
    if SCRIPT_TAG_REGEX.search(value):
        raise ValidationError("Input contains prohibited script or executable content.")
    return value.strip()


class Campaign(PublicIdModel, TimeStampedModel):
    """Marketing campaign grouping for promotional messaging."""

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
    badge_text = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "content_campaign"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.status})"

    def clean(self):
        super().clean()
        if self.name:
            self.name = sanitize_plain_text(self.name)
        if self.badge_text:
            self.badge_text = sanitize_plain_text(self.badge_text)
        if self.description:
            self.description = sanitize_plain_text(self.description)
        if self.start_at and self.end_at and self.start_at >= self.end_at:
            raise ValidationError({"end_at": "Campaign end time must be after start time."})


class ContentBlockQuerySet(models.QuerySet):
    def public_visible(self, now=None):
        """Dynamic query filtering published or scheduled content within active date windows."""
        if now is None:
            now = timezone.now()
        return self.filter(
            models.Q(status=ContentBlock.STATUS_PUBLISHED)
            | models.Q(status=ContentBlock.STATUS_SCHEDULED),
            models.Q(start_at__isnull=True) | models.Q(start_at__lte=now),
            models.Q(end_at__isnull=True) | models.Q(end_at__gt=now),
        ).order_by("sort_order", "-created_at")


class ContentBlock(PublicIdModel, TimeStampedModel):
    """Polymorphic content block for Storefront and CMS editorial placement."""

    TYPE_HERO = "hero"
    TYPE_BANNER = "banner"
    TYPE_ANNOUNCEMENT = "announcement"
    TYPE_PROMO_SECTION = "promotional_section"
    TYPE_CONTENT_SECTION = "content_section"

    TYPE_CHOICES = [
        (TYPE_HERO, "Hero Banner"),
        (TYPE_BANNER, "Promotional Banner"),
        (TYPE_ANNOUNCEMENT, "Announcement Bar"),
        (TYPE_PROMO_SECTION, "Promotional Section"),
        (TYPE_CONTENT_SECTION, "Content Section"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_SCHEDULED = "scheduled"
    STATUS_PUBLISHED = "published"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    content_type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        default=TYPE_CONTENT_SECTION,
        db_index=True,
    )
    body = models.TextField(blank=True, default="")
    image_url = models.CharField(max_length=500, blank=True, default="")
    alt_text = models.CharField(max_length=255, blank=True, default="")
    cta_label = models.CharField(max_length=100, blank=True, default="")
    cta_url = models.CharField(max_length=500, blank=True, default="")

    linked_product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_blocks",
    )
    linked_category = models.ForeignKey(
        "categories.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_blocks",
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_blocks",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    objects = ContentBlockQuerySet.as_manager()

    class Meta:
        db_table = "content_block"
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return f"[{self.content_type}] {self.title} ({self.status})"

    def clean(self):
        super().clean()
        if self.title:
            self.title = sanitize_plain_text(self.title)
        if self.body:
            self.body = sanitize_plain_text(self.body)
        if self.cta_label:
            self.cta_label = sanitize_plain_text(self.cta_label)
        if self.start_at and self.end_at and self.start_at >= self.end_at:
            raise ValidationError({"end_at": "End time must be after start time."})

    def is_currently_visible(self, now=None) -> bool:
        """Helper evaluating current server-side publication window."""
        if self.status not in (self.STATUS_PUBLISHED, self.STATUS_SCHEDULED):
            return False
        if now is None:
            now = timezone.now()
        if self.start_at and self.start_at > now:
            return False
        if self.end_at and self.end_at <= now:
            return False
        return True
