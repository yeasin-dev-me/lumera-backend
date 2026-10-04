"""Serializers for Users, Authentication, and RBAC."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Public customer and user profile serializer."""
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
    """Staff user serializer with assigned permission codes."""
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

    def get_permissions(self, obj) -> list:
        return obj.get_permission_codes()


class CustomerRegistrationSerializer(serializers.Serializer):
    """Validates registration input and creates a new customer."""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=10)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return normalized

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as err:
            raise serializers.ValidationError(list(err.messages))
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            phone=validated_data.get("phone", ""),
            is_staff=False,
            is_active=True,
        )
        return user


class CustomerTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Customer token serializer with account status validation."""

    def validate(self, attrs):
        # Normalize email
        if "email" in attrs:
            attrs["email"] = attrs["email"].strip().lower()
        data = super().validate(attrs)

        if not self.user.is_active:
            raise exceptions.AuthenticationFailed("Account is inactive.")

        data["user"] = UserSerializer(self.user).data
        return data


class CMSTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Token serializer for CMS staff, enforcing is_staff and active status."""

    def validate(self, attrs):
        # Normalize email
        if "email" in attrs:
            attrs["email"] = attrs["email"].strip().lower()
        data = super().validate(attrs)

        if not self.user.is_active:
            raise exceptions.AuthenticationFailed("Account is inactive.")

        if not self.user.is_staff:
            raise exceptions.PermissionDenied("Only authorized staff can log in to the CMS.")

        data["user"] = StaffUserMeSerializer(self.user).data
        return data


class LogoutSerializer(serializers.Serializer):
    """Serializer handling refresh token blacklisting."""
    refresh = serializers.CharField(required=False, allow_blank=True)

    def save(self):
        refresh_token = self.validated_data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                # Silently accept invalid or expired token during logout
                pass
