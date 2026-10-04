"""Shared model abstractions for Lumera."""
import uuid
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model adding created_at and updated_at timestamps."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublicIdModel(models.Model):
    """Abstract model providing a public UUID4 identifier for safe external reference."""
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    class Meta:
        abstract = True
