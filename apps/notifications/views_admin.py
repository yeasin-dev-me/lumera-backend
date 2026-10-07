"""Staff CMS endpoints for notification delivery audit and retry management."""
import uuid
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.common.pagination import StandardResultsSetPagination
from apps.users.permissions import HasPermission
from .models import Notification
from .serializers import AdminNotificationSerializer
from .services import resend_notification


class AdminNotificationListView(APIView):
    """List and filter operational notification delivery records."""

    permission_classes = [HasPermission("notifications.read")]

    def get(self, request):
        queryset = Notification.objects.select_related("order", "user").all()

        delivery_status = request.query_params.get("status")
        if delivery_status:
            queryset = queryset.filter(status=delivery_status)

        event_type = request.query_params.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        channel = request.query_params.get("channel")
        if channel:
            queryset = queryset.filter(channel=channel)

        recipient = request.query_params.get("recipient")
        if recipient:
            queryset = queryset.filter(recipient__icontains=recipient.strip())

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AdminNotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminNotificationDetailView(APIView):
    """Retrieve operational notification delivery details."""

    permission_classes = [HasPermission("notifications.read")]

    def get(self, request, public_id):
        try:
            val = uuid.UUID(str(public_id))
        except (ValueError, TypeError):
            raise exceptions.NotFound("Notification not found.")

        notification = Notification.objects.select_related("order", "user").filter(public_id=val).first()
        if not notification:
            raise exceptions.NotFound("Notification not found.")

        return Response(AdminNotificationSerializer(notification).data, status=status.HTTP_200_OK)


class AdminNotificationResendView(APIView):
    """Idempotently retry or resend a notification."""

    permission_classes = [HasPermission("notifications.manage")]

    def post(self, request, public_id):
        try:
            val = uuid.UUID(str(public_id))
        except (ValueError, TypeError):
            raise exceptions.NotFound("Notification not found.")

        notification = Notification.objects.select_related("order", "user").filter(public_id=val).first()
        if not notification:
            raise exceptions.NotFound("Notification not found.")

        updated = resend_notification(notification)
        return Response(AdminNotificationSerializer(updated).data, status=status.HTTP_200_OK)
