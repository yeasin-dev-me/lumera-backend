"""User and Auth views."""
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .permissions import IsStaffMember
from .serializers import (
    CMSTokenObtainPairSerializer,
    StaffUserMeSerializer,
    UserSerializer,
)


class CustomerMeView(APIView):
    """Returns the authenticated customer's profile."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminMeView(APIView):
    """Returns the authenticated staff member's profile and permissions."""
    permission_classes = [IsStaffMember]

    def get(self, request):
        serializer = StaffUserMeSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CMSLoginView(TokenObtainPairView):
    """Staff login for CMS."""
    serializer_class = CMSTokenObtainPairSerializer


class CustomerLoginView(TokenObtainPairView):
    """Customer login for Storefront."""
    pass


class LumeraTokenRefreshView(TokenRefreshView):
    """JWT Refresh view."""
    pass
