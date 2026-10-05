"""Authoritative business services for Checkout and Orders (ADR-0013, BR-03, BR-08, BR-11)."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import random
import string
from django.db import transaction
from rest_framework import exceptions
from apps.cart.models import Cart, CartItem
from apps.cart.serializers import format_money, TWO_PLACES, CartSerializer
from apps.common.exceptions import InsufficientStock, ProductUnavailable
from apps.products.models import Product
from apps.products.selectors import is_storefront_eligible, primary_image_url
from .models import Order, OrderItem, OrderStatusHistory


def generate_order_number() -> str:
    """Generate a collision-free unique order number in format LUM-YYYYMMDD-XXXXXX."""
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    chars = string.ascii_uppercase + string.digits
    for _ in range(10):
        random_part = "".join(random.choices(chars, k=6))
        candidate = f"LUM-{date_part}-{random_part}"
        if not Order.objects.filter(order_number=candidate).exists():
            return candidate
    # Fallback to microsecond suffix
    return f"LUM-{date_part}-{int(datetime.now(timezone.utc).timestamp() * 1000) % 1000000:06d}"


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

    return order
