"""User, Authentication, and RBAC views."""
from django.db import transaction
from rest_framework import exceptions, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .permissions import HasPermission, IsStaffMember
from .serializers import (
    AddressSerializer,
    CMSTokenObtainPairSerializer,
    CustomerRegistrationSerializer,
    CustomerTokenObtainPairSerializer,
    LogoutSerializer,
    StaffUserMeSerializer,
    UserSerializer,
)


class CustomerRegistrationView(APIView):
    """Customer registration endpoint creating active customer accounts."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CustomerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Issue immediate JWT tokens upon successful registration
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CustomerLoginView(TokenObtainPairView):
    """Customer authentication endpoint returning JWT tokens and user profile."""
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomerTokenObtainPairSerializer


class CustomerLogoutView(APIView):
    """Customer logout endpoint invalidating refresh tokens."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class CustomerMeView(APIView):
    """Returns the authenticated customer's own profile."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomerAddressListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            AddressSerializer(request.user.addresses.all(), many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = AddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            # Lock the owner so concurrent default changes cannot race.
            type(request.user).objects.select_for_update().get(pk=request.user.pk)
            has_default = request.user.addresses.filter(is_default=True).exists()
            wants_default = serializer.validated_data.get("is_default", False) or not has_default
            if wants_default:
                request.user.addresses.filter(is_default=True).update(is_default=False)
            address = serializer.save(
                user=request.user,
                is_default=wants_default,
            )
        return Response(AddressSerializer(address).data, status=status.HTTP_201_CREATED)


class CustomerAddressDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get(self, request, public_id):
        address = request.user.addresses.filter(public_id=public_id).first()
        if not address:
            raise exceptions.NotFound("Address not found.")
        return address

    def _update(self, request, public_id, *, partial):
        address = self._get(request, public_id)
        serializer = AddressSerializer(address, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            type(request.user).objects.select_for_update().get(pk=request.user.pk)
            address = request.user.addresses.select_for_update().get(pk=address.pk)
            if serializer.validated_data.get("is_default") is True:
                request.user.addresses.filter(is_default=True).exclude(pk=address.pk).update(
                    is_default=False
                )
            updated = serializer.save()
        return Response(AddressSerializer(updated).data, status=status.HTTP_200_OK)

    def put(self, request, public_id):
        return self._update(request, public_id, partial=False)

    def patch(self, request, public_id):
        return self._update(request, public_id, partial=True)

    def delete(self, request, public_id):
        address = self._get(request, public_id)
        with transaction.atomic():
            type(request.user).objects.select_for_update().get(pk=request.user.pk)
            address = request.user.addresses.select_for_update().get(pk=address.pk)
            was_default = address.is_default
            address.delete()
            if was_default:
                replacement = request.user.addresses.order_by("-created_at").first()
                if replacement:
                    replacement.is_default = True
                    replacement.save(update_fields=["is_default", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CMSLoginView(TokenObtainPairView):
    """Staff authentication endpoint verifying is_staff and returning permissions."""
    permission_classes = [permissions.AllowAny]
    serializer_class = CMSTokenObtainPairSerializer


class CMSLogoutView(APIView):
    """Staff logout endpoint invalidating refresh tokens."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class AdminMeView(APIView):
    """Returns the authenticated staff member's profile and resolved permissions."""
    permission_classes = [IsStaffMember]

    def get(self, request):
        serializer = StaffUserMeSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LumeraTokenRefreshView(TokenRefreshView):
    """Standardized JWT Refresh endpoint enforcing rotation and blacklist."""
    permission_classes = [permissions.AllowAny]


class AdminTestPermissionView(APIView):
    """Protected admin endpoint requiring specific permission (for RBAC testing)."""
    permission_classes = [HasPermission("products.write")]

    def get(self, request):
        return Response({"status": "authorized", "permission": "products.write"}, status=status.HTTP_200_OK)
