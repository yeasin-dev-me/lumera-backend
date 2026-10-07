"""Storefront public views for Content."""
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import ContentBlock
from .serializers import ContentBlockSerializer, StorefrontHomeContentSerializer


class StorefrontHomeContentView(APIView):
    """Retrieve active content blocks formatted for the Storefront Homepage."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        visible_qs = ContentBlock.objects.public_visible().select_related(
            "linked_product", "linked_category", "campaign"
        )

        hero = visible_qs.filter(content_type=ContentBlock.TYPE_HERO).first()
        announcement = visible_qs.filter(
            content_type=ContentBlock.TYPE_ANNOUNCEMENT
        ).first()
        banners = list(visible_qs.filter(content_type=ContentBlock.TYPE_BANNER))
        sections = list(
            visible_qs.filter(
                content_type__in=[
                    ContentBlock.TYPE_PROMO_SECTION,
                    ContentBlock.TYPE_CONTENT_SECTION,
                ]
            )
        )

        data = {
            "hero": hero,
            "announcement": announcement,
            "banners": banners,
            "sections": sections,
        }
        serializer = StorefrontHomeContentSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StorefrontBannersView(APIView):
    """List active promotional banners and announcements."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        visible_qs = ContentBlock.objects.public_visible().filter(
            content_type__in=[
                ContentBlock.TYPE_BANNER,
                ContentBlock.TYPE_ANNOUNCEMENT,
            ]
        ).select_related("linked_product", "linked_category", "campaign")
        serializer = ContentBlockSerializer(visible_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StorefrontContentDetailView(APIView):
    """Retrieve an active, published content block by slug."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        block = get_object_or_404(
            ContentBlock.objects.public_visible().select_related(
                "linked_product", "linked_category", "campaign"
            ),
            slug=slug,
        )
        serializer = ContentBlockSerializer(block)
        return Response(serializer.data, status=status.HTTP_200_OK)
