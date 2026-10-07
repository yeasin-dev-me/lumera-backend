"""CMS admin views for Content and Campaigns (ADR-0017)."""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.users.permissions import HasPermission
from .models import Campaign, ContentBlock
from .serializers import (
    CampaignSerializer,
    ContentBlockAdminSerializer,
)


class AdminContentListCreateView(generics.ListCreateAPIView):
    """GET /api/v1/admin/content/ - List all content blocks.
    POST /api/v1/admin/content/ - Create a content block.
    """

    serializer_class = ContentBlockAdminSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasPermission("content.manage")()]
        return [HasPermission("content.read")()]

    def get_queryset(self):
        qs = ContentBlock.objects.all().select_related(
            "linked_product", "linked_category", "campaign"
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        content_type_param = self.request.query_params.get("content_type")
        if content_type_param:
            qs = qs.filter(content_type=content_type_param)

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(slug__icontains=search)
                | Q(body__icontains=search)
            )
        return qs.order_by("sort_order", "-created_at")


class AdminContentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET, PATCH, DELETE /api/v1/admin/content/{public_id}/"""

    lookup_field = "public_id"
    serializer_class = ContentBlockAdminSerializer
    queryset = ContentBlock.objects.all().select_related(
        "linked_product", "linked_category", "campaign"
    )

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT", "DELETE"]:
            return [HasPermission("content.manage")()]
        return [HasPermission("content.read")()]

    def perform_destroy(self, instance):
        instance.status = ContentBlock.STATUS_ARCHIVED
        instance.save(update_fields=["status", "updated_at"])


class AdminContentPublishView(APIView):
    """POST /api/v1/admin/content/{public_id}/publish/"""

    permission_classes = [HasPermission("content.manage")]

    def post(self, request, public_id):
        block = get_object_or_404(ContentBlock, public_id=public_id)
        block.status = ContentBlock.STATUS_PUBLISHED
        block.save(update_fields=["status", "updated_at"])
        serializer = ContentBlockAdminSerializer(block)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminContentUnpublishView(APIView):
    """POST /api/v1/admin/content/{public_id}/unpublish/"""

    permission_classes = [HasPermission("content.manage")]

    def post(self, request, public_id):
        block = get_object_or_404(ContentBlock, public_id=public_id)
        block.status = ContentBlock.STATUS_DRAFT
        block.save(update_fields=["status", "updated_at"])
        serializer = ContentBlockAdminSerializer(block)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminContentArchiveView(APIView):
    """POST /api/v1/admin/content/{public_id}/archive/"""

    permission_classes = [HasPermission("content.manage")]

    def post(self, request, public_id):
        block = get_object_or_404(ContentBlock, public_id=public_id)
        block.status = ContentBlock.STATUS_ARCHIVED
        block.save(update_fields=["status", "updated_at"])
        serializer = ContentBlockAdminSerializer(block)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminCampaignListCreateView(generics.ListCreateAPIView):
    """GET, POST /api/v1/admin/campaigns/"""

    serializer_class = CampaignSerializer
    queryset = Campaign.objects.all().order_by("-created_at")

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasPermission("content.manage")()]
        return [HasPermission("content.read")()]


class AdminCampaignDetailView(generics.RetrieveUpdateAPIView):
    """GET, PATCH /api/v1/admin/campaigns/{public_id}/"""

    lookup_field = "public_id"
    serializer_class = CampaignSerializer
    queryset = Campaign.objects.all()

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT"]:
            return [HasPermission("content.manage")()]
        return [HasPermission("content.read")()]
