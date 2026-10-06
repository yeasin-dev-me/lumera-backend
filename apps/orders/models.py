"""Domain models for Orders, OrderItems, and OrderStatusHistory (ADR-0013)."""
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.common.models import PublicIdModel, TimeStampedModel


class Order(PublicIdModel, TimeStampedModel):
    """Authoritative Order model recording purchase-time snapshot (BR-03, BR-11, BR-12)."""

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_PROCESSING = "processing"
    STATUS_SHIPPED = "shipped"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"
    PAYMENT_REFUNDED = "refunded"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_FAILED, "Failed"),
        (PAYMENT_REFUNDED, "Refunded"),
    ]

    order_number = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    payment_status = models.CharField(
        max_length=32,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING,
        db_index=True,
    )
    currency = models.CharField(max_length=3, default="USD")

    # Authoritative monetary fields
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2)

    # Snapshotted shipping information (BR-03, ADR-0013)
    shipping_full_name = models.CharField(max_length=255)
    shipping_phone = models.CharField(max_length=50)
    shipping_address_line1 = models.CharField(max_length=255)
    shipping_address_line2 = models.CharField(max_length=255, blank=True, default="")
    shipping_city = models.CharField(max_length=100)
    shipping_area = models.CharField(max_length=100, blank=True, default="")
    shipping_postal_code = models.CharField(max_length=20, blank=True, default="")
    shipping_country = models.CharField(max_length=100, default="Bangladesh")

    customer_notes = models.TextField(blank=True, default="")

    # Operational fulfillment information (ADR-0015)
    courier = models.CharField(max_length=100, blank=True, default="")
    tracking_number = models.CharField(max_length=100, blank=True, default="")
    tracking_url = models.URLField(max_length=500, blank=True, default="")
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders_order"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Order {self.order_number} ({self.status})"

    def get_item_count(self) -> int:
        return sum(item.quantity for item in self.items.all())


class OrderItem(TimeStampedModel):
    """Immutable purchase-time snapshot of an ordered product (BR-03, ADR-0013)."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    # Historical snapshots independent of catalog changes
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=100)
    product_image = models.CharField(max_length=500, blank=True, default="")

    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "orders_orderitem"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                check=Q(quantity__gt=0),
                name="check_order_item_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.quantity}x {self.product_name} in {self.order.order_number}"


class OrderStatusHistory(models.Model):
    """Append-only audit trail of order status transitions (BR-12)."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.CharField(max_length=32, blank=True, default="")
    to_status = models.CharField(max_length=32)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orders_orderstatushistory"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.order.order_number}: {self.from_status or 'start'} -> {self.to_status}"

    @property
    def actor_type(self) -> str:
        """Dynamically resolve actor category without storing redundant DB column (ADR-0015)."""
        if self.changed_by is None:
            return "system"
        if getattr(self.changed_by, "is_staff", False):
            return "staff"
        return "customer"
