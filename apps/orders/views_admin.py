"""Staff-facing views for Orders in CMS (ADR-0013, CMS Architecture)."""
import uuid
from django.db.models import Q, Sum
from rest_framework import exceptions, generics, status
from rest_framework.response import Response
from apps.common.pagination import StandardResultsSetPagination
from apps.users.permissions import HasPermission
from .models import Order
from .serializers import AdminOrderDetailSerializer, AdminOrderListSerializer


class AdminOrderListView(generics.ListAPIView):
    """GET /api/v1/admin/orders/ - List all customer orders for staff."""

    permission_classes = [HasPermission("orders.read")]
    pagination_class = StandardResultsSetPagination
    serializer_class = AdminOrderListSerializer

    def get_queryset(self):
        queryset = (
            Order.objects.select_related("user")
            .annotate(item_count=Sum("items__quantity"))
            .order_by("-created_at")
        )

        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)

        payment_status_param = self.request.query_params.get("payment_status")
        if payment_status_param:
            queryset = queryset.filter(payment_status=payment_status_param)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search)
                | Q(user__email__icontains=search)
                | Q(shipping_full_name__icontains=search)
            )

        return queryset


class AdminOrderDetailView(generics.RetrieveAPIView):
    """GET /api/v1/admin/orders/{public_id}/ - Retrieve full order detail for staff."""

    permission_classes = [HasPermission("orders.read")]
    serializer_class = AdminOrderDetailSerializer

    def get_object(self):
        identifier = self.kwargs.get("public_id")
        try:
            val = uuid.UUID(str(identifier))
            order = (
                Order.objects.filter(public_id=val)
                .select_related("user")
                .prefetch_related("items__product", "status_history")
                .first()
            )
        except (ValueError, TypeError):
            order = None

        if not order:
            raise exceptions.NotFound("Order not found.")

        return order


class AdminOrderTransitionView(generics.GenericAPIView):
    """POST /api/v1/admin/orders/{public_id}/transition/ - Transition order status."""

    permission_classes = [HasPermission("orders.manage")]
    serializer_class = AdminOrderDetailSerializer

    def post(self, request, public_id):
        try:
            val = uuid.UUID(str(public_id))
            order = Order.objects.filter(public_id=val).first()
        except (ValueError, TypeError):
            order = None

        if not order:
            raise exceptions.NotFound("Order not found.")

        from .serializers import OrderTransitionSerializer
        from .services import transition_order_status

        serializer = OrderTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_order = transition_order_status(
            order=order,
            to_status=serializer.validated_data["to_status"],
            user=request.user,
            reason=serializer.validated_data.get("reason", ""),
            courier=serializer.validated_data.get("courier", ""),
            tracking_number=serializer.validated_data.get("tracking_number", ""),
            tracking_url=serializer.validated_data.get("tracking_url", ""),
        )

        return Response(
            AdminOrderDetailSerializer(updated_order).data,
            status=status.HTTP_200_OK,
        )


class AdminOrderFulfillmentView(generics.GenericAPIView):
    """PATCH /api/v1/admin/orders/{public_id}/fulfillment/ - Update courier/tracking info."""

    permission_classes = [HasPermission("orders.manage")]
    serializer_class = AdminOrderDetailSerializer

    def patch(self, request, public_id):
        try:
            val = uuid.UUID(str(public_id))
            order = Order.objects.filter(public_id=val).first()
        except (ValueError, TypeError):
            order = None

        if not order:
            raise exceptions.NotFound("Order not found.")

        from .serializers import FulfillmentUpdateSerializer
        from .services import update_order_fulfillment

        serializer = FulfillmentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated_order = update_order_fulfillment(
            order=order,
            courier=serializer.validated_data.get("courier", ""),
            tracking_number=serializer.validated_data.get("tracking_number", ""),
            tracking_url=serializer.validated_data.get("tracking_url", ""),
        )

        return Response(
            AdminOrderDetailSerializer(updated_order).data,
            status=status.HTTP_200_OK,
        )
