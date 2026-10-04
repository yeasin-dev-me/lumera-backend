"""User, Authentication, and RBAC views."""
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .permissions import HasPermission, IsStaffMember
from .serializers import (
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
