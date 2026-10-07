"""CMS Admin URLs for Content."""
from django.urls import path
from .views_admin import (
    AdminContentArchiveView,
    AdminContentDetailView,
    AdminContentListCreateView,
    AdminContentPublishView,
    AdminContentUnpublishView,
)

app_name = "content-admin"

urlpatterns = [
    path("", AdminContentListCreateView.as_view(), name="admin-content-list-create"),
    path(
        "<uuid:public_id>/",
        AdminContentDetailView.as_view(),
        name="admin-content-detail",
    ),
    path(
        "<uuid:public_id>/publish/",
        AdminContentPublishView.as_view(),
        name="admin-content-publish",
    ),
    path(
        "<uuid:public_id>/unpublish/",
        AdminContentUnpublishView.as_view(),
        name="admin-content-unpublish",
    ),
    path(
        "<uuid:public_id>/archive/",
        AdminContentArchiveView.as_view(),
        name="admin-content-archive",
    ),
]
