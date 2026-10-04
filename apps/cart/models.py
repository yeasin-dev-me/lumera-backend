"""Cart and Wishlist domain models (ADR-0012).

Design notes:
- Cart/Wishlist are implicit singletons per user (one-to-one); clients never address them by id.
- CartItem stores only product + quantity. Prices are NOT snapshotted here; they are
  recalculated from the current Product on every read (BR-10). The snapshot happens in
  OrderItem at order placement (BR-03).
- Uniqueness of (cart, product) and (wishlist, product) is enforced in the database.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.common.models import TimeStampedModel


class Cart(TimeStampedModel):
    """A customer's single active cart (BR-09)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )

    class Meta:
        db_table = "cart_cart"

    def __str__(self):
        return f"Cart of {self.user_id}"


class CartItem(TimeStampedModel):
    """One cart line per product; quantity only, no price snapshot."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField()

    class Meta:
        db_table = "cart_cartitem"
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                name="uniq_cart_item_cart_product",
            ),
            models.CheckConstraint(
                check=Q(quantity__gt=0),
                name="check_cart_item_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x product {self.product_id} in cart {self.cart_id}"


class Wishlist(TimeStampedModel):
    """A customer's single wishlist."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist",
    )

    class Meta:
        db_table = "cart_wishlist"

    def __str__(self):
        return f"Wishlist of {self.user_id}"


class WishlistItem(TimeStampedModel):
    """Saved product. Does not reserve stock or lock price."""

    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )

    class Meta:
        db_table = "cart_wishlistitem"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["wishlist", "product"],
                name="uniq_wishlist_item_wishlist_product",
            ),
        ]

    def __str__(self):
        return f"Product {self.product_id} in wishlist {self.wishlist_id}"
