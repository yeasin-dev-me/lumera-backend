"""Serializers for Content & Campaign domain."""
from rest_framework import serializers
from apps.categories.models import Category
from apps.products.models import Product
from .models import Campaign, ContentBlock


class ContentBlockSerializer(serializers.ModelSerializer):
    """Public read-only serializer for active content blocks."""

    linked_product_id = serializers.UUIDField(
        source="linked_product.public_id", read_only=True, allow_null=True
    )
    linked_category_slug = serializers.CharField(
        source="linked_category.slug", read_only=True, allow_null=True
    )
    campaign_id = serializers.UUIDField(
        source="campaign.public_id", read_only=True, allow_null=True
    )

    class Meta:
        model = ContentBlock
        fields = [
            "public_id",
            "title",
            "slug",
            "content_type",
            "body",
            "image_url",
            "alt_text",
            "cta_label",
            "cta_url",
            "linked_product_id",
            "linked_category_slug",
            "campaign_id",
            "status",
            "start_at",
            "end_at",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ContentBlockAdminSerializer(serializers.ModelSerializer):
    """Admin serializer for CMS staff content management."""

    linked_product_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    linked_category_slug = serializers.CharField(
        write_only=True, required=False, allow_null=True, allow_blank=True
    )
    campaign_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )

    resolved_linked_product_id = serializers.UUIDField(
        source="linked_product.public_id", read_only=True, allow_null=True
    )
    resolved_linked_category_slug = serializers.CharField(
        source="linked_category.slug", read_only=True, allow_null=True
    )
    resolved_campaign_id = serializers.UUIDField(
        source="campaign.public_id", read_only=True, allow_null=True
    )

    class Meta:
        model = ContentBlock
        fields = [
            "public_id",
            "title",
            "slug",
            "content_type",
            "body",
            "image_url",
            "alt_text",
            "cta_label",
            "cta_url",
            "linked_product_id",
            "linked_category_slug",
            "campaign_id",
            "resolved_linked_product_id",
            "resolved_linked_category_slug",
            "resolved_campaign_id",
            "status",
            "start_at",
            "end_at",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at"]

    def validate_linked_product_id(self, value):
        if value is None:
            return None
        try:
            return Product.objects.get(public_id=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Referenced product does not exist.")

    def validate_linked_category_slug(self, value):
        if not value:
            return None
        try:
            return Category.objects.get(slug=value)
        except Category.DoesNotExist:
            raise serializers.ValidationError("Referenced category does not exist.")

    def validate_campaign_id(self, value):
        if value is None:
            return None
        try:
            return Campaign.objects.get(public_id=value)
        except Campaign.DoesNotExist:
            raise serializers.ValidationError("Referenced campaign does not exist.")

    def validate(self, attrs):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from .models import sanitize_plain_text

        for field in ["title", "body", "cta_label"]:
            val = attrs.get(field)
            if val:
                try:
                    sanitize_plain_text(val)
                except DjangoValidationError as exc:
                    raise serializers.ValidationError({field: exc.messages})
        return attrs

    def create(self, validated_data):
        from django.core.exceptions import ValidationError as DjangoValidationError

        product = validated_data.pop("linked_product_id", None)
        category = validated_data.pop("linked_category_slug", None)
        campaign = validated_data.pop("campaign_id", None)

        if product is not None:
            validated_data["linked_product"] = product
        if category is not None:
            validated_data["linked_category"] = category
        if campaign is not None:
            validated_data["campaign"] = campaign

        instance = super().create(validated_data)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        instance.save()
        return instance

    def update(self, instance, validated_data):
        from django.core.exceptions import ValidationError as DjangoValidationError

        if "linked_product_id" in validated_data:
            instance.linked_product = validated_data.pop("linked_product_id")
        if "linked_category_slug" in validated_data:
            instance.linked_category = validated_data.pop("linked_category_slug")
        if "campaign_id" in validated_data:
            instance.campaign = validated_data.pop("campaign_id")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        instance.save()
        return instance

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Normalize representations for compatibility with contract
        ret["linked_product_id"] = ret.pop("resolved_linked_product_id")
        ret["linked_category_slug"] = ret.pop("resolved_linked_category_slug")
        ret["campaign_id"] = ret.pop("resolved_campaign_id")
        return ret


class StorefrontHomeContentSerializer(serializers.Serializer):
    """Aggregate response for Storefront homepage content slots."""

    hero = ContentBlockSerializer(allow_null=True)
    announcement = ContentBlockSerializer(allow_null=True)
    banners = ContentBlockSerializer(many=True)
    sections = ContentBlockSerializer(many=True)


class CampaignSerializer(serializers.ModelSerializer):
    """Public and admin serializer for promotional campaigns."""

    class Meta:
        model = Campaign
        fields = [
            "public_id",
            "name",
            "slug",
            "description",
            "badge_text",
            "status",
            "start_at",
            "end_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at"]
