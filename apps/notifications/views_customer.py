"""Customer-facing API endpoints for communication preferences and notification history."""
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.common.pagination import StandardResultsSetPagination
from .models import CommunicationPreference, Notification
from .serializers import CommunicationPreferenceSerializer, CustomerNotificationSerializer


class CustomerCommunicationPreferenceView(APIView):
    """Retrieve and update communication preferences for the authenticated customer."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        pref, _ = CommunicationPreference.objects.get_or_create(user=request.user)
        return Response(CommunicationPreferenceSerializer(pref).data, status=status.HTTP_200_OK)

    def patch(self, request):
        pref, _ = CommunicationPreference.objects.get_or_create(user=request.user)
        serializer = CommunicationPreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomerNotificationListView(APIView):
    """List authenticated customer's past transactional notifications with strict user isolation."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = Notification.objects.filter(user=request.user).select_related("order").order_by("-created_at")
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = CustomerNotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
