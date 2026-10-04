"""Serializers for Users and Authentication."""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User


class UserSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "is_active",
            "is_staff",
            "created_at",
        ]
        read_only_fields = ["id", "is_staff", "is_active", "created_at"]


class StaffUserMeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "permissions",
        ]
        read_only_fields = fields

    def get_permissions(self, obj):
        return obj.get_permission_codes()


class CMSTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Token serializer for CMS staff, enforcing staff requirement."""

    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_staff:
            raise serializers.ValidationError({"detail": "Only authorized staff can log in to the CMS."})
        data["user"] = StaffUserMeSerializer(self.user).data
        return data
