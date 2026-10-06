"""Customer-facing views for Checkout and Orders (ADR-0013, BR-11, BR-13)."""
from django.db.models import Sum
from rest_framework import exceptions, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.common.pagination import StandardResultsSetPagination
from .models import Order
from .serializers import (
    CustomerOrderListSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
)
from .services import create_order_from_cart, get_checkout_preview


class CheckoutPreviewView(APIView):
    """GET /api/v1/customer/checkout/ - Authoritative checkout state preview."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        preview_data = get_checkout_preview(request.user)
        return Response(preview_data, status=status.HTTP_200_OK)


class CustomerOrderListView(APIView):
    """GET /api/v1/customer/orders/ - List authenticated customer orders.
    POST /api/v1/customer/orders/ - Create new order from server-side cart.
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        orders = (
            Order.objects.filter(user=request.user)
            .annotate(item_count=Sum("items__quantity"))
            .order_by("-created_at")
        )
        paginator = self.pagination_class()
        paginated_orders = paginator.paginate_queryset(orders, request)
        serializer = CustomerOrderListSerializer(paginated_orders, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shipping_address = serializer.validated_data["shipping_address"]
        customer_notes = serializer.validated_data.get("customer_notes", "")

        order = create_order_from_cart(
            user=request.user,
            shipping_address=shipping_address,
            customer_notes=customer_notes,
        )

        response_serializer = OrderDetailSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class CustomerOrderDetailView(APIView):
    """GET /api/v1/customer/orders/{public_id}/ - Retrieve customer's single order."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, public_id):
        order = (
            Order.objects.filter(user=request.user, public_id=public_id)
            .prefetch_related("items__product", "status_history")
            .first()
        )
        if not order:
            raise exceptions.NotFound("Order not found.")

        serializer = OrderDetailSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomerOrderCancelView(APIView):
    """POST /api/v1/customer/orders/{public_id}/cancel/ - Cancel own unpaid pending order."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, public_id):
        order = (
            Order.objects.filter(user=request.user, public_id=public_id)
            .prefetch_related("items__product", "status_history")
            .first()
        )
        if not order:
            raise exceptions.NotFound("Order not found.")

        from .serializers import OrderCancelSerializer
        from .services import cancel_order

        serializer = OrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reason = serializer.validated_data.get("reason", "Cancelled by customer")
        updated_order = cancel_order(order=order, user=request.user, reason=reason)

        return Response(OrderDetailSerializer(updated_order).data, status=status.HTTP_200_OK)


class CustomerOrderTimelineView(APIView):
    """GET /api/v1/customer/orders/{public_id}/timeline/ - Retrieve order audit progression."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, public_id):
        order = (
            Order.objects.filter(user=request.user, public_id=public_id)
            .prefetch_related("status_history")
            .first()
        )
        if not order:
            raise exceptions.NotFound("Order not found.")

        from .serializers import OrderTimelineItemSerializer

        serializer = OrderTimelineItemSerializer(order.status_history.all(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

