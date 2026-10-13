"""Tests for Step 10: Content, SEO & Marketing foundations (ADR-0017)."""
from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from apps.categories.models import Category
from apps.content.models import ContentBlock
from apps.products.models import Product
from apps.users.models import Role, User


@pytest.fixture
def staff_content_manager():
    """Create staff user with content.read and content.manage permissions."""
    role = Role.objects.create(
        name="content_manager",
        permissions=["content.read", "content.manage"],
    )
    user = User.objects.create_user(
        email="content_admin@example.com",
        password="SecurePassword123!",
        is_staff=True,
    )
    user.roles.add(role)
    return user


@pytest.fixture
def staff_content_reader():
    """Create staff user with only content.read permission."""
    role = Role.objects.create(
        name="content_viewer",
        permissions=["content.read"],
    )
    user = User.objects.create_user(
        email="content_reader@example.com",
        password="SecurePassword123!",
        is_staff=True,
    )
    user.roles.add(role)
    return user


@pytest.fixture
def sample_category():
    return Category.objects.create(
        name="Face Oils",
        slug="face-oils",
        status="active",
    )


@pytest.fixture
def sample_product(sample_category):
    return Product.objects.create(
        name="Luminous Rosehip Seed Oil",
        slug="luminous-rosehip-oil",
        sku="OIL-001",
        category=sample_category,
        price="48.00",
        stock_quantity=50,
        status="active",
        is_visible=True,
    )


@pytest.mark.django_db
def test_draft_content_is_hidden_from_public_storefront():
    ContentBlock.objects.create(
        title="Draft Hero",
        slug="draft-hero",
        content_type=ContentBlock.TYPE_HERO,
        body="Secret upcoming sale",
        status=ContentBlock.STATUS_DRAFT,
    )
    client = APIClient()

    # Detail endpoint returns 404
    detail_res = client.get("/api/v1/content/draft-hero/")
    assert detail_res.status_code == status.HTTP_404_NOT_FOUND

    # Home aggregation does not include draft hero
    home_res = client.get("/api/v1/content/home/")
    assert home_res.status_code == status.HTTP_200_OK
    assert home_res.json()["hero"] is None


@pytest.mark.django_db
def test_published_and_scheduled_content_visibility_window():
    now = timezone.now()

    # Active published banner
    active_banner = ContentBlock.objects.create(
        title="Active Botanicals Banner",
        slug="active-banner",
        content_type=ContentBlock.TYPE_BANNER,
        status=ContentBlock.STATUS_PUBLISHED,
        start_at=now - timedelta(days=1),
        end_at=now + timedelta(days=2),
    )

    # Future scheduled block (not yet live)
    future_block = ContentBlock.objects.create(
        title="Future Promo",
        slug="future-promo",
        content_type=ContentBlock.TYPE_BANNER,
        status=ContentBlock.STATUS_SCHEDULED,
        start_at=now + timedelta(days=1),
        end_at=now + timedelta(days=5),
    )

    # Expired block (past window)
    expired_block = ContentBlock.objects.create(
        title="Expired Promo",
        slug="expired-promo",
        content_type=ContentBlock.TYPE_BANNER,
        status=ContentBlock.STATUS_PUBLISHED,
        start_at=now - timedelta(days=10),
        end_at=now - timedelta(days=1),
    )

    client = APIClient()

    # Active banner is live
    res_active = client.get(f"/api/v1/content/{active_banner.slug}/")
    assert res_active.status_code == status.HTTP_200_OK
    assert res_active.json()["title"] == "Active Botanicals Banner"

    # Future block is 404
    res_future = client.get(f"/api/v1/content/{future_block.slug}/")
    assert res_future.status_code == status.HTTP_404_NOT_FOUND

    # Expired block is 404
    res_expired = client.get(f"/api/v1/content/{expired_block.slug}/")
    assert res_expired.status_code == status.HTTP_404_NOT_FOUND

    # Banners endpoint only returns active
    banners_res = client.get("/api/v1/content/banners/")
    slugs = [b["slug"] for b in banners_res.json()]
    assert "active-banner" in slugs
    assert "future-promo" not in slugs
    assert "expired-promo" not in slugs


@pytest.mark.django_db
def test_customer_cannot_access_admin_content(sample_product):
    customer = User.objects.create_user(
        email="customer@example.com",
        password="CustomerPassword123!",
        is_staff=False,
    )
    client = APIClient()
    client.force_authenticate(user=customer)

    # Customer forbidden from admin content management
    res = client.get("/api/v1/admin/content/")
    assert res.status_code == status.HTTP_403_FORBIDDEN

    post_res = client.post(
        "/api/v1/admin/content/",
        {"title": "Hacked", "slug": "hacked", "content_type": "hero"},
        format="json",
    )
    assert post_res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_staff_content_crud_and_lifecycle_transitions(
    staff_content_manager, sample_product, sample_category
):
    client = APIClient()
    client.force_authenticate(user=staff_content_manager)

    # 1. Create a campaign
    campaign_res = client.post(
        "/api/v1/admin/campaigns/",
        {
            "name": "Summer Glow Campaign",
            "slug": "summer-glow",
            "badge_text": "Summer Glow Exclusive",
            "status": "active",
        },
        format="json",
    )
    assert campaign_res.status_code == status.HTTP_201_CREATED
    campaign_id = campaign_res.json()["public_id"]

    # 2. Create ContentBlock referencing product, category, and campaign
    create_res = client.post(
        "/api/v1/admin/content/",
        {
            "title": "Radiant Rosehip Special",
            "slug": "radiant-rosehip",
            "content_type": "hero",
            "body": "Nourish your moisture barrier with pure cold-pressed botanicals.",
            "image_url": "https://example.com/rosehip.jpg",
            "alt_text": "Rosehip botanical hero",
            "cta_label": "Shop Rosehip Oil",
            "cta_url": "/products/luminous-rosehip-oil",
            "linked_product_id": str(sample_product.public_id),
            "linked_category_slug": sample_category.slug,
            "campaign_id": campaign_id,
            "status": "draft",
            "sort_order": 1,
        },
        format="json",
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    block_data = create_res.json()
    public_id = block_data["public_id"]
    assert block_data["status"] == "draft"
    assert block_data["linked_product_id"] == str(sample_product.public_id)

    # 3. Publish action transition
    pub_res = client.post(f"/api/v1/admin/content/{public_id}/publish/")
    assert pub_res.status_code == status.HTTP_200_OK
    assert pub_res.json()["status"] == "published"

    # Now it is visible on public home endpoint
    anon_client = APIClient()
    home_res = anon_client.get("/api/v1/content/home/")
    assert home_res.status_code == status.HTTP_200_OK
    assert home_res.json()["hero"]["slug"] == "radiant-rosehip"

    # 4. Unpublish action transition
    unpub_res = client.post(f"/api/v1/admin/content/{public_id}/unpublish/")
    assert unpub_res.status_code == status.HTTP_200_OK
    assert unpub_res.json()["status"] == "draft"

    # Public home no longer shows it as hero
    home_after_unpub = anon_client.get("/api/v1/content/home/")
    assert home_after_unpub.json()["hero"] is None


@pytest.mark.django_db
def test_malicious_script_injection_is_rejected(staff_content_manager):
    client = APIClient()
    client.force_authenticate(user=staff_content_manager)

    res = client.post(
        "/api/v1/admin/content/",
        {
            "title": "Clean Title",
            "slug": "xss-test",
            "content_type": "banner",
            "body": "Normal text <script>alert('xss')</script>",
            "status": "draft",
        },
        format="json",
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_storefront_config_exposes_marketing_keys_without_secrets():
    client = APIClient()
    res = client.get("/api/v1/storefront/config/")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["site_name"] == "Penguin Mart"
    assert "announcement_text" in data
    assert "meta_pixel_id" in data
    assert "ga4_measurement_id" in data
    assert "default_seo_title" in data
    # Ensure no secrets leak
    assert "SECRET_KEY" not in data
    assert "password" not in data
