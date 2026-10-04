"""Views for Customer Cart and Wishlist API."""
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import (
    CartItemCreateSerializer,
    CartItemUpdateSerializer,
    CartSerializer,
    WishlistItemCreateSerializer,
    WishlistSerializer,
)
from .services import (
    add_item_to_cart,
    add_item_to_wishlist,
    clear_customer_cart,
    get_customer_cart,
    get_customer_wishlist,
    remove_cart_item,
    remove_wishlist_item,
    update_cart_item_quantity,
)


class CustomerCartView(APIView):
    """Retrieve or clear the authenticated customer's cart."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart = get_customer_cart(request.user)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    def delete(self, request):
        clear_customer_cart(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerCartItemCreateView(APIView):
    """Add a product to the authenticated customer's cart."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data["product_id"]
        quantity = serializer.validated_data.get("quantity", 1)

        cart, created = add_item_to_cart(request.user, product_id, quantity)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(CartSerializer(cart).data, status=status_code)


class CustomerCartItemDetailView(APIView):
    """Update quantity or remove a product line in customer's cart."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, product_id):
        serializer = CartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart = update_cart_item_quantity(
            request.user,
            product_id,
            serializer.validated_data["quantity"],
        )
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    def delete(self, request, product_id):
        remove_cart_item(request.user, product_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerWishlistView(APIView):
    """Retrieve the authenticated customer's wishlist."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        wishlist = get_customer_wishlist(request.user)
        return Response(WishlistSerializer(wishlist).data, status=status.HTTP_200_OK)


class CustomerWishlistItemCreateView(APIView):
    """Add a product to the authenticated customer's wishlist."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = WishlistItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data["product_id"]
        wishlist = add_item_to_wishlist(request.user, product_id)
        return Response(WishlistSerializer(wishlist).data, status=status.HTTP_201_CREATED)


class CustomerWishlistItemDetailView(APIView):
    """Remove a product from the authenticated customer's wishlist."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, product_id):
        remove_wishlist_item(request.user, product_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
