"""Serializers for Cart and Wishlist domain."""
from decimal import Decimal, ROUND_HALF_UP
from rest_framework import serializers
from apps.products.models import Product
from apps.products.selectors import is_storefront_eligible, primary_image_url
from .models import Cart, CartItem, Wishlist, WishlistItem


TWO_PLACES = Decimal("0.01")


def format_money(amount: Decimal | str | float) -> str:
    """Format decimal amount to strict 2 fraction digits string."""
    dec = Decimal(str(amount)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return f"{dec:.2f}"


class CartProductSerializer(serializers.ModelSerializer):
    """Product summary inside cart/wishlist items."""

    price = serializers.SerializerMethodField()
    discount_price = serializers.SerializerMethodField()
    effective_price = serializers.SerializerMethodField()
    primary_image = serializers.SerializerMethodField()
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "public_id",
            "name",
            "slug",
            "primary_image",
            "price",
            "discount_price",
            "effective_price",
            "stock_quantity",
            "is_in_stock",
        ]
        read_only_fields = fields

    def get_price(self, obj: Product) -> str:
        return format_money(obj.price)

    def get_discount_price(self, obj: Product) -> str | None:
        if obj.discount_price is not None:
            return format_money(obj.discount_price)
        return None

    def get_effective_price(self, obj: Product) -> str:
        return format_money(obj.effective_price)

    def get_primary_image(self, obj: Product) -> str | None:
        return primary_image_url(obj)


class CartItemSerializer(serializers.ModelSerializer):
    """Cart item with authoritatively computed pricing and availability."""

    product = CartProductSerializer(read_only=True)
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    availability_status = serializers.SerializerMethodField()
    is_purchasable = serializers.SerializerMethodField()
    added_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "product",
            "quantity",
            "unit_price",
            "line_total",
            "availability_status",
            "is_purchasable",
            "added_at",
        ]
        read_only_fields = fields

    def _get_status(self, obj: CartItem) -> str:
        cached = getattr(obj, "_computed_status", None)
        if cached is not None:
            return cached

        product = obj.product
        if not is_storefront_eligible(product):
            status = "unavailable"
        elif product.stock_quantity <= 0:
            status = "out_of_stock"
        elif obj.quantity > product.stock_quantity:
            status = "insufficient_stock"
        else:
            status = "available"

        obj._computed_status = status
        return status

    def get_availability_status(self, obj: CartItem) -> str:
        return self._get_status(obj)

    def get_is_purchasable(self, obj: CartItem) -> bool:
        return self._get_status(obj) == "available"

    def get_unit_price(self, obj: CartItem) -> str:
        return format_money(obj.product.effective_price)

    def get_line_total(self, obj: CartItem) -> str:
        unit = Decimal(str(obj.product.effective_price))
        total = (unit * Decimal(str(obj.quantity))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        return format_money(total)


class CartSerializer(serializers.ModelSerializer):
    """Full customer cart with authoritative subtotal and summary."""

    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    has_unavailable_items = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "items",
            "item_count",
            "subtotal",
            "total",
            "currency",
            "has_unavailable_items",
            "updated_at",
        ]
        read_only_fields = fields

    def _compute_totals(self, obj: Cart):
        if hasattr(obj, "_totals_cache"):
            return obj._totals_cache

        items = list(obj.items.all())
        total_subtotal = Decimal("0.00")
        total_count = 0
        has_unavailable = False

        for item in items:
            total_count += item.quantity
            product = item.product
            if not is_storefront_eligible(product):
                status = "unavailable"
            elif product.stock_quantity <= 0:
                status = "out_of_stock"
            elif item.quantity > product.stock_quantity:
                status = "insufficient_stock"
            else:
                status = "available"
            item._computed_status = status

            if status == "available":
                unit = Decimal(str(product.effective_price))
                line = (unit * Decimal(str(item.quantity))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                total_subtotal += line
            else:
                has_unavailable = True

        res = {
            "item_count": total_count,
            "subtotal": format_money(total_subtotal),
            "total": format_money(total_subtotal),
            "currency": "USD",
            "has_unavailable_items": has_unavailable,
        }
        obj._totals_cache = res
        return res

    def get_item_count(self, obj: Cart) -> int:
        return self._compute_totals(obj)["item_count"]

    def get_subtotal(self, obj: Cart) -> str:
        return self._compute_totals(obj)["subtotal"]

    def get_total(self, obj: Cart) -> str:
        return self._compute_totals(obj)["total"]

    def get_currency(self, obj: Cart) -> str:
        return self._compute_totals(obj)["currency"]

    def get_has_unavailable_items(self, obj: Cart) -> bool:
        return self._compute_totals(obj)["has_unavailable_items"]


class CartItemCreateSerializer(serializers.Serializer):
    """Input serializer for adding product to cart."""

    product_id = serializers.UUIDField(required=True)
    quantity = serializers.IntegerField(required=False, default=1, min_value=1, max_value=20)


class CartItemUpdateSerializer(serializers.Serializer):
    """Input serializer for updating cart line quantity."""

    quantity = serializers.IntegerField(required=True, min_value=1, max_value=20)


class WishlistItemSerializer(serializers.ModelSerializer):
    """Single saved wishlist item."""

    product = CartProductSerializer(read_only=True)
    is_available = serializers.SerializerMethodField()
    added_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = WishlistItem
        fields = ["product", "is_available", "added_at"]
        read_only_fields = fields

    def get_is_available(self, obj: WishlistItem) -> bool:
        return is_storefront_eligible(obj.product) and obj.product.is_in_stock


class WishlistSerializer(serializers.ModelSerializer):
    """Customer wishlist representation."""

    items = WishlistItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Wishlist
        fields = ["items", "item_count"]
        read_only_fields = fields

    def get_item_count(self, obj: Wishlist) -> int:
        return obj.items.count()


class WishlistItemCreateSerializer(serializers.Serializer):
    """Input serializer for adding item to wishlist."""

    product_id = serializers.UUIDField(required=True)
