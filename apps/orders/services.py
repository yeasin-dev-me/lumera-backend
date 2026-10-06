"""Authoritative business services for Checkout and Orders (ADR-0013, BR-03, BR-08, BR-11)."""
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, ROUND_HALF_UP
import random
import string
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions
from apps.cart.models import Cart, CartItem
from apps.cart.serializers import format_money, TWO_PLACES, CartSerializer
from apps.common.exceptions import ConflictError, InsufficientStock, ProductUnavailable
from apps.notifications.models import Notification
from apps.notifications.services import safe_dispatch_order_notification
from apps.products.models import Product
from apps.products.selectors import is_storefront_eligible, primary_image_url
from .models import Order, OrderItem, OrderStatusHistory


def generate_order_number() -> str:
    """Generate a collision-free unique order number in format LUM-YYYYMMDD-XXXXXX."""
    date_part = datetime.now(dt_timezone.utc).strftime("%Y%m%d")
    chars = string.ascii_uppercase + string.digits
    for _ in range(10):
        random_part = "".join(random.choices(chars, k=6))
        candidate = f"LUM-{date_part}-{random_part}"
        if not Order.objects.filter(order_number=candidate).exists():
            return candidate
    # Fallback to microsecond suffix
    return f"LUM-{date_part}-{int(datetime.now(dt_timezone.utc).timestamp() * 1000) % 1000000:06d}"


def get_checkout_preview(user) -> dict:
    """Return authoritative checkout preview without reserving stock or mutating cart."""
    cart, _ = Cart.objects.get_or_create(user=user)
    cart_obj = (
        Cart.objects.filter(pk=cart.pk)
        .prefetch_related(
            "items__product__images",
            "items__product__category",
        )
        .first()
    )

    items = list(cart_obj.items.all()) if cart_obj else []
    subtotal = Decimal("0.00")
    shipping_cost = Decimal("0.00")
    discount_total = Decimal("0.00")
    is_ready = len(items) > 0

    for item in items:
        product = item.product
        if not is_storefront_eligible(product) or product.stock_quantity < item.quantity:
            is_ready = False
            item._computed_status = "unavailable" if not is_storefront_eligible(product) else "insufficient_stock"
        else:
            item._computed_status = "available"
            unit = Decimal(str(product.effective_price)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            line = (unit * Decimal(str(item.quantity))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            subtotal += line

    total = (subtotal + shipping_cost - discount_total).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    cart_data = CartSerializer(cart_obj).data

    return {
        "cart": cart_data,
        "subtotal": format_money(subtotal),
        "shipping_cost": format_money(shipping_cost),
        "discount_total": format_money(discount_total),
        "total": format_money(total),
        "currency": "USD",
        "is_ready_for_checkout": is_ready,
        "customer": {
            "email": user.email,
            "full_name": getattr(user, "full_name", user.email),
            "phone": getattr(user, "phone", "") or "",
        },
    }


def create_order_from_cart(user, shipping_address: dict, customer_notes: str = "") -> Order:
    """Atomic, row-locked order creation, stock deduction, and cart clearing (ADR-0013).

    Step 1. Lock customer's cart
    Step 2. Read cart items and lock referenced products
    Step 3. Validate product eligibility and live stock
    Step 4. Calculate authoritative price snapshots and line totals
    Step 5. Persist Order and OrderItems
    Step 6. Deduct stock quantities
    Step 7. Clear cart items
    """
    with transaction.atomic():
        # 1. Lock customer's cart
        cart = Cart.objects.select_for_update().filter(user=user).first()
        if not cart:
            raise exceptions.ValidationError(
                {"cart": ["Cart does not exist. Add items before checking out."]}
            )

        cart_items = list(
            CartItem.objects.select_for_update()
            .filter(cart=cart)
            .select_related("product")
        )
        if not cart_items:
            raise exceptions.ValidationError(
                {"cart": ["Your cart is empty. Add items before checking out."]}
            )

        # 2. Lock referenced products to prevent concurrent overselling (BR-08)
        product_ids = [item.product_id for item in cart_items]
        locked_products = {
            p.id: p
            for p in Product.objects.select_for_update()
            .filter(id__in=product_ids)
            .select_related("category")
        }

        # 3. Validate eligibility and stock for every item
        subtotal = Decimal("0.00")
        lines_to_create = []

        for item in cart_items:
            product = locked_products.get(item.product_id)
            if not product or not is_storefront_eligible(product):
                prod_name = item.product.name if item.product else "Item"
                raise ProductUnavailable(
                    f"Product '{prod_name}' is no longer available for purchase."
                )

            if product.stock_quantity < item.quantity:
                raise InsufficientStock(
                    f"Insufficient stock for '{product.name}'. "
                    f"Requested: {item.quantity}, Available: {product.stock_quantity}."
                )

            # 4. Derive immutable snapshot fields
            unit_price = Decimal(str(product.effective_price)).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            line_total = (unit_price * Decimal(str(item.quantity))).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            subtotal += line_total

            lines_to_create.append(
                {
                    "product": product,
                    "product_name": product.name,
                    "product_sku": product.sku,
                    "product_image": primary_image_url(product) or "",
                    "unit_price": unit_price,
                    "quantity": item.quantity,
                    "line_total": line_total,
                }
            )

        shipping_cost = Decimal("0.00")
        discount_total = Decimal("0.00")
        total = (subtotal + shipping_cost - discount_total).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        order_number = generate_order_number()

        # 5. Create Order
        order = Order.objects.create(
            order_number=order_number,
            user=user,
            status=Order.STATUS_PENDING,
            payment_status=Order.PAYMENT_PENDING,
            currency="USD",
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            discount_total=discount_total,
            total=total,
            shipping_full_name=shipping_address["full_name"],
            shipping_phone=shipping_address["phone"],
            shipping_address_line1=shipping_address["address"],
            shipping_address_line2=shipping_address.get("address_line2", "") or "",
            shipping_city=shipping_address["city"],
            shipping_area=shipping_address.get("area", "") or "",
            shipping_postal_code=shipping_address.get("postal_code", "") or "",
            shipping_country=shipping_address.get("country", "Bangladesh") or "Bangladesh",
            customer_notes=customer_notes.strip() if customer_notes else "",
        )

        # 6. Create OrderItems and deduct stock
        for line in lines_to_create:
            OrderItem.objects.create(
                order=order,
                product=line["product"],
                product_name=line["product_name"],
                product_sku=line["product_sku"],
                product_image=line["product_image"],
                unit_price=line["unit_price"],
                quantity=line["quantity"],
                line_total=line["line_total"],
            )
            # Deduct stock atomically
            prod = line["product"]
            prod.stock_quantity = prod.stock_quantity - line["quantity"]
            prod.save(update_fields=["stock_quantity", "updated_at"])

        # 7. Record initial lifecycle history
        OrderStatusHistory.objects.create(
            order=order,
            from_status="",
            to_status=Order.STATUS_PENDING,
            changed_by=user,
            reason="Order placed by customer",
        )

        # 8. Clear customer's cart
        cart.items.all().delete()
        cart.save(update_fields=["updated_at"])

        # 9. Dispatch order placed notification (ADR-0015)
        safe_dispatch_order_notification(order, Notification.EVENT_ORDER_PLACED)

    return order


LEGAL_TRANSITIONS = {
    Order.STATUS_PENDING: [Order.STATUS_CONFIRMED, Order.STATUS_CANCELLED],
    Order.STATUS_CONFIRMED: [Order.STATUS_PROCESSING, Order.STATUS_CANCELLED],
    Order.STATUS_PROCESSING: [Order.STATUS_SHIPPED, Order.STATUS_CANCELLED],
    Order.STATUS_SHIPPED: [Order.STATUS_DELIVERED],
    Order.STATUS_DELIVERED: [],
    Order.STATUS_CANCELLED: [],
}


def transition_order_status(
    order: Order,
    to_status: str,
    user=None,
    reason: str = "",
    courier: str = "",
    tracking_number: str = "",
    tracking_url: str = "",
) -> Order:
    """Authoritatively transition order status enforcing state machine and business rules (ADR-0015)."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)

        if order.status in [Order.STATUS_DELIVERED, Order.STATUS_CANCELLED]:
            raise ConflictError(
                f"Order is in terminal state '{order.status}' and cannot be transitioned."
            )

        if to_status == Order.STATUS_CANCELLED:
            return cancel_order(order=order, user=user, reason=reason)

        allowed = LEGAL_TRANSITIONS.get(order.status, [])
        if to_status not in allowed:
            raise ConflictError(
                f"Illegal state transition from '{order.status}' to '{to_status}'. Legal next states: {allowed}."
            )

        # Payment prerequisite for fulfillment progression (ADR-0015)
        if to_status in [Order.STATUS_PROCESSING, Order.STATUS_SHIPPED]:
            if order.payment_status != Order.PAYMENT_PAID:
                raise ConflictError(
                    f"Order must be paid before transitioning to '{to_status}'. Current payment status is '{order.payment_status}'."
                )

        # Shipping requires courier and tracking info
        if to_status == Order.STATUS_SHIPPED:
            courier_val = str(courier or order.courier or "").strip()
            tracking_val = str(tracking_number or order.tracking_number or "").strip()
            if not courier_val or not tracking_val:
                raise exceptions.ValidationError(
                    {"courier": ["Both courier and tracking number are required when shipping an order."]}
                )
            order.courier = courier_val
            order.tracking_number = tracking_val
            if tracking_url:
                order.tracking_url = str(tracking_url).strip()
            order.shipped_at = timezone.now()

        if to_status == Order.STATUS_DELIVERED:
            order.delivered_at = timezone.now()

        from_status = order.status
        order.status = to_status

        update_fields = ["status", "updated_at"]
        if to_status == Order.STATUS_SHIPPED:
            update_fields.extend(["courier", "tracking_number", "tracking_url", "shipped_at"])
        elif to_status == Order.STATUS_DELIVERED:
            update_fields.append("delivered_at")

        order.save(update_fields=update_fields)

        OrderStatusHistory.objects.create(
            order=order,
            from_status=from_status,
            to_status=to_status,
            changed_by=user,
            reason=reason or f"Transitioned to {to_status}",
        )

        event_map = {
            Order.STATUS_CONFIRMED: Notification.EVENT_PAYMENT_CONFIRMED,
            Order.STATUS_PROCESSING: Notification.EVENT_ORDER_PROCESSING,
            Order.STATUS_SHIPPED: Notification.EVENT_ORDER_SHIPPED,
            Order.STATUS_DELIVERED: Notification.EVENT_ORDER_DELIVERED,
        }
        if to_status in event_map:
            safe_dispatch_order_notification(order, event_map[to_status])

        return order


def update_order_fulfillment(
    order: Order,
    courier: str = "",
    tracking_number: str = "",
    tracking_url: str = "",
) -> Order:
    """Update order shipping and tracking metadata without altering status (ADR-0015)."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        update_fields = ["updated_at"]
        if courier is not None and courier != "":
            order.courier = str(courier).strip()
            update_fields.append("courier")
        if tracking_number is not None and tracking_number != "":
            order.tracking_number = str(tracking_number).strip()
            update_fields.append("tracking_number")
        if tracking_url is not None:
            order.tracking_url = str(tracking_url).strip()
            update_fields.append("tracking_url")

        order.save(update_fields=update_fields)
        return order


def cancel_order(order: Order, user=None, reason: str = "") -> Order:
    """Cancel order and atomically restore inventory without altering payment records (ADR-0015)."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)

        if order.status in [Order.STATUS_DELIVERED, Order.STATUS_CANCELLED]:
            raise ConflictError(f"Cannot cancel order in terminal state '{order.status}'.")

        is_staff = user and getattr(user, "is_staff", False)
        if not is_staff:
            # Customer self-serve cancellation authority check
            if order.status != Order.STATUS_PENDING or order.payment_status != Order.PAYMENT_PENDING:
                raise ConflictError("Customers may only cancel unpaid orders in pending status.")

        if order.status not in [Order.STATUS_PENDING, Order.STATUS_CONFIRMED, Order.STATUS_PROCESSING]:
            raise ConflictError(f"Orders in state '{order.status}' cannot be cancelled.")

        from_status = order.status
        order.status = Order.STATUS_CANCELLED
        # Note: payment_status remains untouched (no auto-refunds per ADR-0015)
        order.save(update_fields=["status", "updated_at"])

        # Atomically restore stock quantity for all line items (ADR-0015)
        items = list(order.items.select_related("product"))
        product_ids = [item.product_id for item in items if item.product_id]
        if product_ids:
            locked_products = {
                p.id: p
                for p in Product.objects.select_for_update().filter(id__in=product_ids)
            }
            for item in items:
                if item.product_id and item.product_id in locked_products:
                    prod = locked_products[item.product_id]
                    prod.stock_quantity = prod.stock_quantity + item.quantity
                    prod.save(update_fields=["stock_quantity", "updated_at"])

        OrderStatusHistory.objects.create(
            order=order,
            from_status=from_status,
            to_status=Order.STATUS_CANCELLED,
            changed_by=user,
            reason=reason or "Order cancelled",
        )

        safe_dispatch_order_notification(order, Notification.EVENT_ORDER_CANCELLED)
        return order
