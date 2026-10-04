"""Serializers for Categories domain."""
from rest_framework import serializers
from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    """Full Category serializer for Storefront and CMS."""

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "image_url",
            "status",
            "sort_order",
            "seo_title",
            "seo_description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_slug(self, value):
        slug = value.strip().lower()
        query = Category.objects.filter(slug=slug)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("A category with this slug already exists.")
        return slug


class CategorySummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for embedding inside products."""

    class Meta:
        model = Category
        fields = ["id", "name", "slug"]
