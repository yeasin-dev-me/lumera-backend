"""CMS Admin URLs for Campaigns."""
from django.urls import path
from .views_admin import AdminCampaignDetailView, AdminCampaignListCreateView

app_name = "campaigns-admin"

urlpatterns = [
    path("", AdminCampaignListCreateView.as_view(), name="admin-campaign-list-create"),
    path(
        "<uuid:public_id>/",
        AdminCampaignDetailView.as_view(),
        name="admin-campaign-detail",
    ),
]
