"""Serializers for customer communication preferences and operational notifications (ADR-0018)."""
from rest_framework import serializers
from .models import CommunicationPreference, Notification


class CommunicationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for authenticated customer communication preferences."""

    order_updates_email = serializers.BooleanField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CommunicationPreference
        fields = [
            "marketing_email",
            "marketing_sms",
            "order_updates_email",
            "updated_at",
        ]


class CustomerNotificationSerializer(serializers.ModelSerializer):
    """Customer-facing notification audit item serializer."""

    order_number = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "public_id",
            "event_type",
            "channel",
            "status",
            "subject",
            "order_number",
            "created_at",
            "sent_at",
        ]

    def get_order_number(self, obj: Notification) -> str | None:
        return obj.order.order_number if obj.order else None


class AdminNotificationSerializer(serializers.ModelSerializer):
    """CMS operational notification delivery serializer."""

    order_number = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "public_id",
            "recipient",
            "event_type",
            "channel",
            "status",
            "subject",
            "attempt_count",
            "provider_message_id",
            "error_message",
            "order_number",
            "created_at",
            "sent_at",
            "failed_at",
        ]

    def get_order_number(self, obj: Notification) -> str | None:
        return obj.order.order_number if obj.order else None
