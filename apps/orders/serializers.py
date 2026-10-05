"""Serializers for Orders and Checkout domain (ADR-0013)."""
from rest_framework import serializers
from apps.cart.serializers import format_money
from .models import Order, OrderItem, OrderStatusHistory


class ShippingAddressInputSerializer(serializers.Serializer):
    """Input validation for shipping address at checkout."""

    full_name = serializers.CharField(min_length=2, max_length=255, required=True)
    phone = serializers.CharField(min_length=7, max_length=50, required=True)
    address = serializers.CharField(min_length=3, max_length=255, required=True)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    city = serializers.CharField(min_length=2, max_length=100, required=True)
    area = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    country = serializers.CharField(max_length=100, required=False, default="Bangladesh")


class OrderCreateSerializer(serializers.Serializer):
    """Input serializer for POST /api/v1/customer/orders/."""

    shipping_address = ShippingAddressInputSerializer(required=True)
    customer_notes = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        default="",
    )


class OrderItemDetailSerializer(serializers.ModelSerializer):
    """Snapshot details of an ordered item."""

    product_public_id = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_public_id",
            "product_name",
            "product_sku",
            "product_image",
            "unit_price",
            "quantity",
            "line_total",
        ]
        read_only_fields = fields

    def get_product_public_id(self, obj: OrderItem) -> str | None:
        return str(obj.product.public_id) if obj.product else None

    def get_unit_price(self, obj: OrderItem) -> str:
        return format_money(obj.unit_price)

    def get_line_total(self, obj: OrderItem) -> str:
        return format_money(obj.line_total)


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    """Status transition history log entry."""

    class Meta:
        model = OrderStatusHistory
        fields = [
            "from_status",
            "to_status",
            "reason",
            "created_at",
        ]
        read_only_fields = fields


class CustomerOrderListSerializer(serializers.ModelSerializer):
    """Customer-facing order summary for list views."""

    total = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "public_id",
            "order_number",
            "status",
            "payment_status",
            "item_count",
            "total",
            "currency",
            "created_at",
        ]
        read_only_fields = fields

    def get_total(self, obj: Order) -> str:
        return format_money(obj.total)

    def get_item_count(self, obj: Order) -> int:
        val = getattr(obj, "item_count", None)
        if val is not None:
            return val
        return obj.get_item_count()


class OrderDetailSerializer(serializers.ModelSerializer):
    """Full historical order detail with snapshots (BR-03)."""

    subtotal = serializers.SerializerMethodField()
    shipping_cost = serializers.SerializerMethodField()
    discount_total = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()
    items = OrderItemDetailSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "public_id",
            "order_number",
            "status",
            "payment_status",
            "currency",
            "subtotal",
            "shipping_cost",
            "discount_total",
            "total",
            "shipping_address",
            "customer_notes",
            "items",
            "status_history",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_subtotal(self, obj: Order) -> str:
        return format_money(obj.subtotal)

    def get_shipping_cost(self, obj: Order) -> str:
        return format_money(obj.shipping_cost)

    def get_discount_total(self, obj: Order) -> str:
        return format_money(obj.discount_total)

    def get_total(self, obj: Order) -> str:
        return format_money(obj.total)

    def get_shipping_address(self, obj: Order) -> dict:
        return {
            "full_name": obj.shipping_full_name,
            "phone": obj.shipping_phone,
            "address": obj.shipping_address_line1,
            "address_line2": obj.shipping_address_line2,
            "city": obj.shipping_city,
            "area": obj.shipping_area,
            "postal_code": obj.shipping_postal_code,
            "country": obj.shipping_country,
        }


class AdminOrderListSerializer(CustomerOrderListSerializer):
    """Staff order listing with customer summary."""

    customer_email = serializers.CharField(source="user.email", read_only=True)
    customer_name = serializers.SerializerMethodField()

    class Meta(CustomerOrderListSerializer.Meta):
        fields = CustomerOrderListSerializer.Meta.fields + [
            "customer_email",
            "customer_name",
        ]

    def get_customer_name(self, obj: Order) -> str:
        return getattr(obj.user, "full_name", obj.user.email)


class AdminOrderDetailSerializer(OrderDetailSerializer):
    """Staff order detail with customer profile data."""

    customer = serializers.SerializerMethodField()

    class Meta(OrderDetailSerializer.Meta):
        fields = OrderDetailSerializer.Meta.fields + ["customer"]

    def get_customer(self, obj: Order) -> dict:
        return {
            "public_id": str(obj.user.public_id),
            "email": obj.user.email,
            "full_name": getattr(obj.user, "full_name", obj.user.email),
            "phone": getattr(obj.user, "phone", "") or "",
        }
