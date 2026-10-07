"""Serializers for Orders and Checkout domain (ADR-0013)."""
from rest_framework import serializers
from apps.cart.serializers import format_money
from .models import Order, OrderItem, OrderStatusHistory, ReturnRequest, ReturnRequestItem


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


class ReturnRequestSerializer(serializers.ModelSerializer):
    order_public_id = serializers.UUIDField(source="order.public_id", read_only=True)
    items = serializers.SerializerMethodField()

    class Meta:
        model = ReturnRequest
        fields = ["public_id", "order_public_id", "reason", "status", "staff_note", "items", "created_at"]
        read_only_fields = ["public_id", "order_public_id", "status", "staff_note", "created_at"]

    def get_items(self, obj):
        return [
            {
                "order_item_id": str(item.order_item.id),
                "product_name": item.order_item.product_name,
                "quantity": item.quantity,
            }
            for item in obj.items.select_related("order_item").all()
        ]


class CustomerReturnRequestSerializer(ReturnRequestSerializer):
    class Meta(ReturnRequestSerializer.Meta):
        fields = ["public_id", "order_public_id", "reason", "status", "items", "created_at"]
        read_only_fields = ["public_id", "order_public_id", "status", "created_at"]


class ReturnRequestCreateSerializer(serializers.Serializer):
    order_public_id = serializers.UUIDField()
    reason = serializers.CharField(min_length=3, max_length=1000)
    items = serializers.ListField(child=serializers.DictField(), min_length=1)

    def validate_items(self, value):
        normalized = []
        seen = set()
        for item in value:
            try:
                order_item_id = int(item["order_item_id"])
                quantity = int(item["quantity"])
            except (KeyError, TypeError, ValueError):
                raise serializers.ValidationError("Each item requires order_item_id and quantity.")
            if quantity <= 0 or order_item_id in seen:
                raise serializers.ValidationError("Return item quantities must be positive and unique.")
            seen.add(order_item_id)
            normalized.append({"order_item_id": order_item_id, "quantity": quantity})
        return normalized


class ReturnReviewSerializer(serializers.Serializer):
    staff_note = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class AdminOrderReportSerializer(serializers.Serializer):
    """Stable aggregate shape for CMS reporting screens."""

    orders_count = serializers.IntegerField()
    paid_orders_count = serializers.IntegerField()
    gross_sales = serializers.CharField()
    refunded_total = serializers.CharField()
    currency = serializers.CharField()


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

    actor_type = serializers.CharField(read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = [
            "from_status",
            "to_status",
            "actor_type",
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
    payment = serializers.SerializerMethodField()

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
            "courier",
            "tracking_number",
            "tracking_url",
            "shipped_at",
            "delivered_at",
            "payment",
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

    def get_payment(self, obj: Order) -> dict | None:
        payment = obj.payments.order_by("-created_at").first()
        if not payment:
            return None
        return {
            "public_id": str(payment.public_id),
            "gateway": payment.gateway,
            "method": payment.method,
            "status": payment.status,
            "amount": format_money(payment.amount),
            "currency": payment.currency,
            "provider_transaction_id": payment.provider_transaction_id,
            "provider_reference": payment.provider_reference,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
            "created_at": payment.created_at.isoformat(),
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
    """Staff order detail with customer profile data and payment attempt history."""

    customer = serializers.SerializerMethodField()
    payment_attempts = serializers.SerializerMethodField()

    class Meta(OrderDetailSerializer.Meta):
        fields = OrderDetailSerializer.Meta.fields + ["customer", "payment_attempts"]

    def get_customer(self, obj: Order) -> dict:
        return {
            "public_id": str(obj.user.public_id),
            "email": obj.user.email,
            "full_name": getattr(obj.user, "full_name", obj.user.email),
            "phone": getattr(obj.user, "phone", "") or "",
        }

    def get_payment_attempts(self, obj: Order) -> list[dict]:
        payment = obj.payments.prefetch_related("attempts").order_by("-created_at").first()
        if not payment:
            return []
        return [
            {
                "public_id": str(att.public_id),
                "attempt_number": att.attempt_number,
                "gateway": att.gateway,
                "status": att.status,
                "amount": format_money(att.amount),
                "currency": att.currency,
                "provider_transaction_id": att.provider_transaction_id,
                "error_message": att.error_message,
                "created_at": att.created_at.isoformat(),
            }
            for att in payment.attempts.all()
        ]


class OrderTransitionSerializer(serializers.Serializer):
    """Payload serializer for admin order state transitions (ADR-0015)."""

    to_status = serializers.ChoiceField(
        choices=[
            Order.STATUS_CONFIRMED,
            Order.STATUS_PROCESSING,
            Order.STATUS_SHIPPED,
            Order.STATUS_DELIVERED,
            Order.STATUS_CANCELLED,
        ]
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    courier = serializers.CharField(required=False, allow_blank=True, default="")
    tracking_number = serializers.CharField(required=False, allow_blank=True, default="")
    tracking_url = serializers.URLField(required=False, allow_blank=True, default="")


class FulfillmentUpdateSerializer(serializers.Serializer):
    """Payload serializer for updating courier/tracking information without status change."""

    courier = serializers.CharField(required=False, allow_blank=True, default="")
    tracking_number = serializers.CharField(required=False, allow_blank=True, default="")
    tracking_url = serializers.URLField(required=False, allow_blank=True, default="")


class OrderCancelSerializer(serializers.Serializer):
    """Payload serializer for customer order cancellation."""

    reason = serializers.CharField(required=False, allow_blank=True, default="Order cancelled by customer")


class OrderTimelineItemSerializer(serializers.ModelSerializer):
    """Customer-facing order audit trail item with dynamic actor resolution."""

    actor_type = serializers.CharField(read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = [
            "from_status",
            "to_status",
            "actor_type",
            "reason",
            "created_at",
        ]
        read_only_fields = fields
