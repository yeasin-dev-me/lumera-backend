"""Serializers for Products domain."""
from decimal import Decimal
from rest_framework import serializers
from apps.categories.models import Category
from apps.categories.serializers import CategorySummarySerializer
from .models import Product, ProductImage


class ProductImageSerializer(serializers.ModelSerializer):
    """Product gallery image serializer."""

    class Meta:
        model = ProductImage
        fields = ["id", "image_url", "alt_text", "sort_order", "is_primary"]
        read_only_fields = ["id"]


class ProductListItemSerializer(serializers.ModelSerializer):
    """Optimized serializer for product catalog listings."""

    category = CategorySummarySerializer(read_only=True)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    discount_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=True,
        allow_null=True,
        required=False,
    )
    effective_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=True,
        read_only=True,
    )
    is_in_stock = serializers.BooleanField(read_only=True)
    primary_image = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "public_id",
            "name",
            "slug",
            "sku",
            "category",
            "price",
            "discount_price",
            "effective_price",
            "stock_quantity",
            "is_in_stock",
            "status",
            "is_visible",
            "is_featured",
            "sort_order",
            "primary_image",
            "created_at",
        ]
        read_only_fields = fields


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for product view with full gallery and metadata."""

    category = CategorySummarySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    discount_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=True,
        allow_null=True,
        required=False,
    )
    effective_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=True,
        read_only=True,
    )
    is_in_stock = serializers.BooleanField(read_only=True)
    primary_image = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "public_id",
            "name",
            "slug",
            "sku",
            "category",
            "description",
            "price",
            "discount_price",
            "effective_price",
            "stock_quantity",
            "is_in_stock",
            "status",
            "is_visible",
            "is_featured",
            "sort_order",
            "seo_title",
            "seo_description",
            "images",
            "primary_image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "public_id",
            "effective_price",
            "is_in_stock",
            "primary_image",
            "created_at",
            "updated_at",
        ]


class ProductImageInputSerializer(serializers.Serializer):
    """Input serializer for nested image creation/updates."""

    image_url = serializers.CharField(max_length=500)
    alt_text = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    sort_order = serializers.IntegerField(required=False, default=0)
    is_primary = serializers.BooleanField(required=False, default=False)


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Authoritative product creation and update serializer for CMS."""

    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        write_only=True,
    )
    images = ProductImageInputSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "public_id",
            "name",
            "slug",
            "sku",
            "category_id",
            "description",
            "price",
            "discount_price",
            "stock_quantity",
            "status",
            "is_visible",
            "is_featured",
            "sort_order",
            "seo_title",
            "seo_description",
            "images",
        ]
        read_only_fields = ["id", "public_id"]

    def validate_price(self, value):
        if value < Decimal("0.00"):
            raise serializers.ValidationError("Price cannot be negative.")
        return value

    def validate_stock_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock quantity cannot be negative.")
        return value

    def validate_slug(self, value):
        slug = value.strip().lower()
        query = Product.objects.filter(slug=slug)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("A product with this slug already exists.")
        return slug

    def validate_sku(self, value):
        sku = value.strip().upper()
        query = Product.objects.filter(sku=sku)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("A product with this SKU already exists.")
        return sku

    def validate(self, attrs):
        price = attrs.get("price")
        if price is None and self.instance:
            price = self.instance.price

        discount_price = attrs.get("discount_price")
        if "discount_price" not in attrs and self.instance:
            discount_price = self.instance.discount_price

        if discount_price is not None:
            if discount_price < Decimal("0.00"):
                raise serializers.ValidationError({"discount_price": "Discount price cannot be negative."})
            if price is not None and discount_price >= price:
                raise serializers.ValidationError(
                    {"discount_price": "Discount price must be less than regular price."}
                )

        category = attrs.get("category")
        if category and category.status == Category.STATUS_ARCHIVED:
            status = attrs.get("status", getattr(self.instance, "status", None))
            if status == Product.STATUS_ACTIVE:
                raise serializers.ValidationError(
                    {"category_id": "Cannot assign an active product to an archived category."}
                )

        return attrs

    def create(self, validated_data):
        images_data = validated_data.pop("images", [])
        product = Product.objects.create(**validated_data)
        for img_info in images_data:
            ProductImage.objects.create(product=product, **img_info)
        return product

    def update(self, instance, validated_data):
        images_data = validated_data.pop("images", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if images_data is not None:
            instance.images.all().delete()
            for img_info in images_data:
                ProductImage.objects.create(product=instance, **img_info)

        return instance
