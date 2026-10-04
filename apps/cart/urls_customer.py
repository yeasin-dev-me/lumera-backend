"""Customer Cart & Wishlist URLs."""
from django.urls import path
from .views import (
    CustomerCartItemCreateView,
    CustomerCartItemDetailView,
    CustomerCartView,
    CustomerWishlistItemCreateView,
    CustomerWishlistItemDetailView,
    CustomerWishlistView,
)

urlpatterns = [
    # Cart
    path("cart/", CustomerCartView.as_view(), name="customer-cart"),
    path("cart/items/", CustomerCartItemCreateView.as_view(), name="customer-cart-items"),
    path("cart/items/<uuid:product_id>/", CustomerCartItemDetailView.as_view(), name="customer-cart-item-detail"),

    # Wishlist
    path("wishlist/", CustomerWishlistView.as_view(), name="customer-wishlist"),
    path("wishlist/items/", CustomerWishlistItemCreateView.as_view(), name="customer-wishlist-items"),
    path("wishlist/items/<uuid:product_id>/", CustomerWishlistItemDetailView.as_view(), name="customer-wishlist-item-detail"),
]
