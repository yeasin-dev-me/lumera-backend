"""Customer-facing views for Checkout and Orders (ADR-0013, BR-11, BR-13)."""
from django.db import transaction
from django.db.models import Sum
from rest_framework import exceptions, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.common.pagination import StandardResultsSetPagination
from .models import Order, ReturnRequest, ReturnRequestItem
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


class CustomerReturnRequestListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .serializers import CustomerReturnRequestSerializer
        return Response(CustomerReturnRequestSerializer(
            request.user.return_requests.select_related("order"), many=True
        ).data)

    def post(self, request):
        from .serializers import CustomerReturnRequestSerializer, ReturnRequestCreateSerializer
        serializer = ReturnRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = Order.objects.filter(
            public_id=serializer.validated_data["order_public_id"], user=request.user
        ).first()
        if not order:
            raise exceptions.NotFound("Order not found.")
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            if order.status != Order.STATUS_DELIVERED:
                raise exceptions.ValidationError("Only delivered orders can be returned.")
            if ReturnRequest.objects.filter(
                order=order, user=request.user,
                status__in=[ReturnRequest.STATUS_REQUESTED, ReturnRequest.STATUS_APPROVED],
            ).exists():
                raise exceptions.ValidationError("An active return already exists for this order.")
            result = ReturnRequest.objects.create(
                order=order, user=request.user, reason=serializer.validated_data["reason"]
            )
            order_items = {
                item.id: item
                for item in order.items.select_for_update().filter(
                    id__in=[item["order_item_id"] for item in serializer.validated_data["items"]]
                )
            }
            if len(order_items) != len(serializer.validated_data["items"]):
                raise exceptions.ValidationError("One or more return items do not belong to this order.")
            for item_data in serializer.validated_data["items"]:
                order_item = order_items[item_data["order_item_id"]]
                returned_quantity = (
                    ReturnRequestItem.objects.filter(
                        order_item=order_item,
                    )
                    .exclude(return_request__status=ReturnRequest.STATUS_CANCELLED)
                    .aggregate(total=Sum("quantity"))["total"]
                    or 0
                )
                remaining_quantity = order_item.quantity - returned_quantity
                if item_data["quantity"] > remaining_quantity:
                    raise exceptions.ValidationError(
                        "Requested quantity exceeds the remaining returnable quantity."
                    )
                ReturnRequestItem.objects.create(
                    return_request=result,
                    order_item=order_item,
                    quantity=item_data["quantity"],
                )

        from apps.notifications.models import Notification
        from apps.notifications.services import safe_dispatch_return_notification
        safe_dispatch_return_notification(result, Notification.EVENT_RETURN_REQUESTED)

        return Response(CustomerReturnRequestSerializer(result).data, status=status.HTTP_201_CREATED)


class CustomerReturnRequestDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, public_id):
        result = (
            request.user.return_requests.select_related("order")
            .prefetch_related("items__order_item")
            .filter(public_id=public_id)
            .first()
        )
        if not result:
            raise exceptions.NotFound("Return request not found.")
        from .serializers import CustomerReturnRequestSerializer
        return Response(CustomerReturnRequestSerializer(result).data, status=status.HTTP_200_OK)
