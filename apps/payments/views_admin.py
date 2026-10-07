from rest_framework import status
from apps.common.pagination import StandardResultsSetPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.users.permissions import HasPermission
from .models import Refund
from .serializers import RefundCreateSerializer, RefundSerializer
from .services import create_refund


class AdminRefundView(APIView):
    permission_classes = [HasPermission("payments.refund")]

    def get(self, request):
        refunds = Refund.objects.select_related("payment", "order").all()
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(refunds, request)
        return paginator.get_paginated_response(RefundSerializer(page, many=True).data)

    def post(self, request):
        serializer = RefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refund = create_refund(
            payment_public_id=serializer.validated_data["payment_public_id"],
            amount=serializer.validated_data["amount"],
            reason=serializer.validated_data["reason"],
            processed_by=request.user,
        )
        from apps.notifications.models import Notification
        from apps.notifications.services import safe_dispatch_refund_notification
        safe_dispatch_refund_notification(refund, Notification.EVENT_REFUND_INITIATED)
        return Response(RefundSerializer(refund).data, status=status.HTTP_201_CREATED)
