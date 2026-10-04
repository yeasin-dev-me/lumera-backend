"""Authoritative Cart and Wishlist business services."""
from uuid import UUID
from django.db import transaction
from rest_framework import exceptions
from apps.common.exceptions import ConflictError, InsufficientStock, ProductUnavailable
from apps.products.selectors import is_storefront_eligible, storefront_eligible_products
from .models import Cart, CartItem, Wishlist, WishlistItem


def get_customer_cart(user) -> Cart:
    """Retrieve customer's cart with pre-fetched relations."""
    cart, _ = Cart.objects.get_or_create(user=user)
    return (
        Cart.objects.filter(pk=cart.pk)
        .prefetch_related(
            "items__product__images",
            "items__product__category",
        )
        .first()
    )


def add_item_to_cart(user, product_public_id: UUID, quantity: int = 1) -> tuple[Cart, bool]:
    """Add a product to the customer's cart, merging if existing (BR-07, BR-09, BR-10a)."""
    # 1. Product must exist and be storefront-eligible (BR-04)
    product = (
        storefront_eligible_products()
        .filter(public_id=product_public_id)
        .select_related("category")
        .first()
    )
    if not product:
        raise exceptions.NotFound("Product not found or currently unavailable.")

    # 2. Transactionally add or merge line
    with transaction.atomic():
        cart, _ = Cart.objects.select_for_update().get_or_create(user=user)
        cart_item = (
            CartItem.objects.select_for_update()
            .filter(cart=cart, product=product)
            .first()
        )

        if cart_item:
            target_quantity = cart_item.quantity + quantity
            if target_quantity > 20:
                raise exceptions.ValidationError(
                    {"quantity": ["Cannot exceed maximum quantity of 20 items per product line."]}
                )
            if target_quantity > product.stock_quantity:
                raise InsufficientStock("Requested quantity exceeds available stock.")

            cart_item.quantity = target_quantity
            cart_item.save(update_fields=["quantity", "updated_at"])
            created = False
        else:
            if quantity > 20:
                raise exceptions.ValidationError(
                    {"quantity": ["Cannot exceed maximum quantity of 20 items per product line."]}
                )
            if quantity > product.stock_quantity:
                raise InsufficientStock("Requested quantity exceeds available stock.")

            cart_item = CartItem.objects.create(
                cart=cart,
                product=product,
                quantity=quantity,
            )
            created = True

        cart.save(update_fields=["updated_at"])

    return get_customer_cart(user), created


def update_cart_item_quantity(user, product_public_id: UUID, quantity: int) -> Cart:
    """Update absolute quantity of a product line in customer's cart (BR-07, BR-09)."""
    # 1. Look up cart and item
    cart = Cart.objects.filter(user=user).first()
    if not cart:
        raise exceptions.NotFound("Cart item not found.")

    with transaction.atomic():
        cart_item = (
            CartItem.objects.select_for_update()
            .filter(cart=cart, product__public_id=product_public_id)
            .select_related("product__category")
            .first()
        )
        if not cart_item:
            raise exceptions.NotFound("Product not found in cart.")

        product = cart_item.product

        # 2. Check product eligibility (BR-10b)
        if not is_storefront_eligible(product):
            raise ProductUnavailable("This product is no longer available for purchase.")

        # 3. Stock validation
        if quantity > product.stock_quantity:
            raise InsufficientStock("Requested quantity exceeds available stock.")

        cart_item.quantity = quantity
        cart_item.save(update_fields=["quantity", "updated_at"])
        cart.save(update_fields=["updated_at"])

    return get_customer_cart(user)


def remove_cart_item(user, product_public_id: UUID) -> None:
    """Idempotently remove a product line from customer's cart."""
    CartItem.objects.filter(
        cart__user=user,
        product__public_id=product_public_id,
    ).delete()


def clear_customer_cart(user) -> None:
    """Idempotently remove all lines from customer's cart."""
    cart = Cart.objects.filter(user=user).first()
    if cart:
        cart.items.all().delete()


def get_customer_wishlist(user) -> Wishlist:
    """Retrieve customer's wishlist with pre-fetched relations."""
    wishlist, _ = Wishlist.objects.get_or_create(user=user)
    return (
        Wishlist.objects.filter(pk=wishlist.pk)
        .prefetch_related(
            "items__product__images",
            "items__product__category",
        )
        .first()
    )


def add_item_to_wishlist(user, product_public_id: UUID) -> Wishlist:
    """Add a product to the customer's wishlist (BR-10d)."""
    product = (
        storefront_eligible_products()
        .filter(public_id=product_public_id)
        .first()
    )
    if not product:
        raise exceptions.NotFound("Product not found or currently unavailable.")

    with transaction.atomic():
        wishlist, _ = Wishlist.objects.select_for_update().get_or_create(user=user)
        if WishlistItem.objects.filter(wishlist=wishlist, product=product).exists():
            raise ConflictError("Product is already in your wishlist.")

        WishlistItem.objects.create(wishlist=wishlist, product=product)
        wishlist.save(update_fields=["updated_at"])

    return get_customer_wishlist(user)


def remove_wishlist_item(user, product_public_id: UUID) -> None:
    """Idempotently remove a product from customer's wishlist."""
    WishlistItem.objects.filter(
        wishlist__user=user,
        product__public_id=product_public_id,
    ).delete()
