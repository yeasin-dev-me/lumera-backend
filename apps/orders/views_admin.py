"""Staff-facing views for Orders in CMS (ADR-0013, CMS Architecture)."""
import uuid
from decimal import Decimal
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils.dateparse import parse_datetime
from rest_framework import exceptions, generics, status
from rest_framework.response import Response
from apps.common.pagination import StandardResultsSetPagination
from apps.users.permissions import HasPermission
from .models import Order, ReturnRequest
from .serializers import (
    AdminOrderDetailSerializer,
    AdminOrderListSerializer,
    AdminOrderReportSerializer,
    ReturnReviewSerializer,
    ReturnRequestSerializer,
)


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


class AdminOrderReportView(generics.GenericAPIView):
    """GET /api/v1/admin/reports/orders/ - aggregate order/payment reporting."""

    permission_classes = [HasPermission("reports.read")]
    serializer_class = AdminOrderReportSerializer

    def get(self, request):
        orders = Order.objects.all()
        currency = request.query_params.get("currency")
        if currency:
            orders = orders.filter(currency=currency.upper())
        start = parse_datetime(request.query_params.get("from", "")) if request.query_params.get("from") else None
        end = parse_datetime(request.query_params.get("to", "")) if request.query_params.get("to") else None
        if start:
            orders = orders.filter(created_at__gte=start)
        if end:
            orders = orders.filter(created_at__lt=end)
        totals = orders.aggregate(
            orders_count=Count("id"),
            paid_orders_count=Count("id", filter=Q(payment_status=Order.PAYMENT_PAID)),
        )
        from apps.payments.models import Payment, Refund
        paid_payments = Payment.objects.filter(status=Payment.STATUS_PAID)
        if currency:
            paid_payments = paid_payments.filter(currency=currency.upper())
        if start:
            paid_payments = paid_payments.filter(paid_at__gte=start)
        if end:
            paid_payments = paid_payments.filter(paid_at__lt=end)
        gross_sales = paid_payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        refunds = Refund.objects.filter(status=Refund.STATUS_SUCCEEDED)
        if start:
            refunds = refunds.filter(created_at__gte=start)
        if end:
            refunds = refunds.filter(created_at__lt=end)
        if currency:
            refunds = refunds.filter(currency=currency.upper())
        refunded_total = refunds.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        data = {
            "orders_count": totals["orders_count"] or 0,
            "paid_orders_count": totals["paid_orders_count"] or 0,
            "gross_sales": str(gross_sales),
            "refunded_total": str(refunded_total),
            "currency": currency.upper() if currency else "mixed",
        }
        return Response(AdminOrderReportSerializer(data).data, status=status.HTTP_200_OK)


class AdminReturnListView(generics.ListAPIView):
    permission_classes = [HasPermission("orders.read")]
    serializer_class = ReturnRequestSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = ReturnRequest.objects.select_related("order", "user").prefetch_related(
            "items__order_item"
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset


class AdminReturnDetailView(generics.RetrieveAPIView):
    permission_classes = [HasPermission("orders.read")]
    serializer_class = ReturnRequestSerializer

    def get_queryset(self):
        return ReturnRequest.objects.select_related("order", "user").prefetch_related(
            "items__order_item"
        )

    def get_object(self):
        try:
            value = uuid.UUID(str(self.kwargs["public_id"]))
        except (ValueError, TypeError):
            raise exceptions.NotFound("Return request not found.")
        result = self.get_queryset().filter(public_id=value).first()
        if not result:
            raise exceptions.NotFound("Return request not found.")
        return result


class AdminReturnTransitionView(generics.GenericAPIView):
    permission_classes = [HasPermission("orders.manage")]
    serializer_class = ReturnReviewSerializer

    allowed_transitions = {
        "approve": (ReturnRequest.STATUS_REQUESTED, ReturnRequest.STATUS_APPROVED),
        "reject": (ReturnRequest.STATUS_REQUESTED, ReturnRequest.STATUS_REJECTED),
        "receive": (ReturnRequest.STATUS_APPROVED, ReturnRequest.STATUS_RECEIVED),
    }

    def post(self, request, public_id, action):
        if action not in self.allowed_transitions:
            raise exceptions.NotFound("Return action not found.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            value = uuid.UUID(str(public_id))
        except (ValueError, TypeError):
            raise exceptions.NotFound("Return request not found.")
        with transaction.atomic():
            return_request = (
                ReturnRequest.objects.select_for_update()
                .filter(public_id=value)
                .first()
            )
            if not return_request:
                raise exceptions.NotFound("Return request not found.")
            expected, target = self.allowed_transitions[action]
            if return_request.status != expected:
                raise exceptions.ValidationError("Invalid return state transition.")
            return_request.status = target
            note = serializer.validated_data.get("staff_note", "")
            if note:
                return_request.staff_note = note
            return_request.save(update_fields=["status", "staff_note", "updated_at"])

        action_event_map = {
            "approve": "return_approved",
            "reject": "return_rejected",
            "receive": "return_received",
        }
        if action in action_event_map:
            from apps.notifications.services import safe_dispatch_return_notification
            safe_dispatch_return_notification(return_request, action_event_map[action])

        return Response(ReturnRequestSerializer(return_request).data, status=status.HTTP_200_OK)


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
