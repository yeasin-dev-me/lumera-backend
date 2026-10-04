"""Admin Categories URLs."""
from django.urls import path
from .views import AdminCategoryDetailView, AdminCategoryListCreateView

urlpatterns = [
    path("", AdminCategoryListCreateView.as_view(), name="admin-category-list-create"),
    path("<str:id>/", AdminCategoryDetailView.as_view(), name="admin-category-detail"),
]
