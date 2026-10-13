"""Management command to seed comprehensive demo and test data for Lumera.

Populates realistic wholesale botanical skincare catalog:
- 6 active categories
- 12 active products with images, wholesale pricing, discount pricing, stock
- 3 active content blocks (hero, announcement, promotional section)
- 2 active campaigns
- 1 staff administrator (staff@lumera.internal / StaffPassword123!)
- 1 demo wholesale customer (customer@lumera.internal / CustomerPassword123!)
- 2 historical demo orders with tracking and item snapshots
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import User, Role
from apps.categories.models import Category
from apps.products.models import Product, ProductImage
from apps.content.models import ContentBlock, Campaign
from apps.orders.models import Order, OrderItem, OrderStatusHistory


class Command(BaseCommand):
    help = "Seed realistic demo data for Storefront, CMS, and API testing."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Lumera demo data..."))

        # 1. Staff and Super Admin Role
        role, _ = Role.objects.get_or_create(
            name="super_admin",
            defaults={
                "description": "Full access to all operations",
                "permissions": ["*"],
            },
        )

        staff_email = "staff@lumera.internal"
        staff_user, _ = User.objects.get_or_create(
            email=staff_email,
            defaults={
                "first_name": "Eleanor",
                "last_name": "Vane",
                "is_staff": True,
                "is_active": True,
            },
        )
        staff_user.set_password("StaffPassword123!")
        staff_user.is_staff = True
        staff_user.is_active = True
        staff_user.roles.add(role)
        staff_user.save()
        self.stdout.write(self.style.SUCCESS(f"Staff user ready: {staff_email}"))

        # 2. Demo Customer
        customer_email = "customer@lumera.internal"
        customer_user, _ = User.objects.get_or_create(
            email=customer_email,
            defaults={
                "first_name": "Sophia",
                "last_name": "Laurent",
                "phone": "+1-555-019-2834",
                "is_staff": False,
                "is_active": True,
            },
        )
        customer_user.set_password("CustomerPassword123!")
        customer_user.is_active = True
        customer_user.save()
        self.stdout.write(self.style.SUCCESS(f"Demo customer ready: {customer_email}"))

        # 3. Categories
        categories_data = [
            {
                "name": "Cleansers & Toners",
                "slug": "cleansers-toners",
                "description": "Gentle, pH-balanced botanical purifying cleansers and hydrating flower mists.",
                "image_url": "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=600&q=80",
                "sort_order": 1,
                "seo_title": "Wholesale Botanical Cleansers & Toners | Penguin Mart",
                "seo_description": "Clean, pH-balanced botanical skincare cleansers for professional wholesale clients.",
            },
            {
                "name": "Serums & Elixirs",
                "slug": "serums-elixirs",
                "description": "High-potency botanical actives, hyaluronic complexes, and brightening vitamin serums.",
                "image_url": "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=600&q=80",
                "sort_order": 2,
                "seo_title": "Active Botanical Serums & Treatment Elixirs | Penguin Mart",
                "seo_description": "Concentrated clinical serums formulated with organic botanicals and bio-peptides.",
            },
            {
                "name": "Moisturizers & Creams",
                "slug": "moisturizers-creams",
                "description": "Rich ceramide balms, peptide barrier creams, and weightless hydration gels.",
                "image_url": "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=600&q=80",
                "sort_order": 3,
                "seo_title": "Wholesale Barrier Creams & Moisturizers | Penguin Mart",
                "seo_description": "Nourishing lipid and ceramide facial moisturizers for retail spas and aesthetics salons.",
            },
            {
                "name": "Facial Oils & Essences",
                "slug": "facial-oils-essences",
                "description": "Cold-pressed botanical seed oils and bio-fermented nourishing facial essences.",
                "image_url": "https://images.unsplash.com/photo-1608248597359-0010f37f3747?auto=format&fit=crop&w=600&q=80",
                "sort_order": 4,
                "seo_title": "Cold-Pressed Botanical Facial Oils | Penguin Mart",
                "seo_description": "Pure plant lipids, squalane, and rosehip elixirs for deep cellular radiance.",
            },
            {
                "name": "Eye & Lip Treatments",
                "slug": "eye-lip-treatments",
                "description": "Caffeine peptide eye creams and antioxidant squalane lip repair treatments.",
                "image_url": "https://images.unsplash.com/photo-1512290900672-1f55b9e078c1?auto=format&fit=crop&w=600&q=80",
                "sort_order": 5,
                "seo_title": "Targeted Eye & Lip Botanical Treatments | Penguin Mart",
                "seo_description": "Specialized restorative care for delicate ocular and perioral zones.",
            },
            {
                "name": "Sunscreen & Barrier Shield",
                "slug": "sunscreen-barrier-shield",
                "description": "Broad-spectrum invisible mineral SPF 50 shields infused with calming centella.",
                "image_url": "https://images.unsplash.com/photo-1598440947619-2c35fc9aa908?auto=format&fit=crop&w=600&q=80",
                "sort_order": 6,
                "seo_title": "Mineral Sunscreen & Environmental Defense | Penguin Mart",
                "seo_description": "Clean zinc oxide sunscreens providing photo-protection and microbiome defense.",
            },
        ]

        cat_map = {}
        for cdata in categories_data:
            cat, _ = Category.objects.update_or_create(
                slug=cdata["slug"],
                defaults={
                    "name": cdata["name"],
                    "description": cdata["description"],
                    "image_url": cdata["image_url"],
                    "status": Category.STATUS_ACTIVE,
                    "sort_order": cdata["sort_order"],
                    "seo_title": cdata["seo_title"],
                    "seo_description": cdata["seo_description"],
                },
            )
            cat_map[cdata["slug"]] = cat
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(cat_map)} active categories."))

        # 4. Products & Product Images
        products_data = [
            {
                "name": "Botanical Hydration Mist & Toner",
                "slug": "botanical-hydration-mist",
                "sku": "LUM-CL-001",
                "category": cat_map["cleansers-toners"],
                "price": Decimal("38.00"),
                "discount_price": Decimal("32.00"),
                "stock_quantity": 450,
                "is_featured": True,
                "sort_order": 1,
                "description": (
                    "An ultra-fine restorative floral mist with organic Bulgarian damask rose water, "
                    "chamomile hydrosol, and bioactive hyaluronic acid. Restores dermal pH instantly."
                ),
                "seo_title": "Botanical Hydration Mist & Rose Floral Toner | Penguin Mart",
                "seo_description": "Organic rose water mist with bio-fermented hyaluronic acid for glowing hydration.",
                "images": [
                    "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1608248597359-0010f37f3747?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "name": "Gentle Chamomile Foaming Cleanser",
                "slug": "gentle-chamomile-foaming-cleanser",
                "sku": "LUM-CL-002",
                "category": cat_map["cleansers-toners"],
                "price": Decimal("42.00"),
                "discount_price": None,
                "stock_quantity": 320,
                "is_featured": False,
                "sort_order": 2,
                "description": (
                    "Sulfate-free coconut glucoside cleanser infused with wild German chamomile, "
                    "aloe vera juice, and cucumber distillate. Melts away impurities without stripping moisture."
                ),
                "seo_title": "Gentle Chamomile Foaming Cleanser | Penguin Mart",
                "seo_description": "Sulfate-free soothing facial cleanser suitable for hypersensitive and barrier-compromised skin.",
                "images": [
                    "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "name": "Luminous Glow Bio-Active Facial Oil",
                "slug": "luminous-glow-facial-oil",
                "sku": "LUM-OIL-001",
                "category": cat_map["facial-oils-essences"],
                "price": Decimal("78.00"),
                "discount_price": Decimal("65.00"),
                "stock_quantity": 180,
                "is_featured": True,
                "sort_order": 3,
                "description": (
                    "Golden cold-pressed lipid elixir combining Chilean rosehip seed, Kalahari melon, "
                    "sea buckthorn fruit, and sugarcane squalane. Delivers luminous non-greasy radiance."
                ),
                "seo_title": "Luminous Glow Bio-Active Facial Oil | Penguin Mart",
                "seo_description": "Cold-pressed rosehip and sea buckthorn botanical face oil for barrier lipid replenishment.",
                "images": [
                    "https://images.unsplash.com/photo-1608248597359-0010f37f3747?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "name": "Cellular Vitamin C Radiance Serum",
                "slug": "cellular-vitamin-c-radiance-serum",
                "sku": "LUM-SR-001",
                "category": cat_map["serums-elixirs"],
                "price": Decimal("85.00"),
                "discount_price": Decimal("72.00"),
                "stock_quantity": 520,
                "is_featured": True,
                "sort_order": 4,
                "description": (
                    "Clinical 15% stabilized tetrahexyldecyl ascorbate coupled with ferulic acid, "
                    "Kakadu plum extract, and vitamin E. Defends against oxidative damage and brightens complexion."
                ),
                "seo_title": "Cellular Vitamin C Radiance Serum | Penguin Mart",
                "seo_description": "Clinical 15% THD ascorbate antioxidant serum with Kakadu plum and botanical ferulic acid.",
                "images": [
                    "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "name": "Multi-Molecular Hyaluronic Acid Serum",
                "slug": "multi-molecular-hyaluronic-serum",
                "sku": "LUM-SR-002",
                "category": cat_map["serums-elixirs"],
                "price": Decimal("68.00"),
                "discount_price": None,
                "stock_quantity": 290,
                "is_featured": False,
                "sort_order": 5,
                "description": (
                    "Five molecular weights of sodium hyaluronate combined with Tremella mushroom extract "
                    "and panthenol B5 for deep epidermis hydration and plumpness."
                ),
                "seo_title": "Multi-Molecular Hyaluronic Acid Serum | Penguin Mart",
                "seo_description": "Five molecular weights of hyaluronic acid plus snow mushroom for deep cell hydration.",
                "images": [
                    "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "name": "Ceramide Barrier Defense Cream",
                "slug": "ceramide-barrier-defense-cream",
                "sku": "LUM-CR-001",
                "category": cat_map["moisturizers-creams"],
                "price": Decimal("74.00"),
                "discount_price": Decimal("62.00"),
                "stock_quantity": 410,
                "is_featured": True,
                "sort_order": 6,
                "description": (
                    "Physiological 3:1:1 lipid ratio of ceramide NP/AP/EOP, plant cholesterol, and essential fatty acids. "
                    "Clinically repairs damaged skin barriers within 48 hours."
                ),
                "seo_title": "Ceramide Barrier Defense Cream | Penguin Mart",
                "seo_description": "Clinical biomimetic ceramide complex for eczema-prone, sensitized skin barrier recovery.",
                "images": [
                    "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "name": "Velvet Cloud Dew Peptide Gel Cream",
                "slug": "velvet-cloud-dew-gel-cream",
                "sku": "LUM-CR-002",
                "category": cat_map["moisturizers-creams"],
                "price": Decimal("66.00"),
                "discount_price": None,
                "stock_quantity": 215,
                "is_featured": False,
                "sort_order": 7,
                "description": (
                    "Weightless water-gel moisturizer packed with signal hexapeptides, green tea catechins, "
                    "and marine algae polysaccharides. Perfect base for makeup and hot climates."
                ),
                "seo_title": "Velvet Cloud Dew Peptide Gel Cream | Penguin Mart",
                "seo_description": "Weightless peptide water-burst gel cream delivering 72-hour non-comedogenic moisture.",
                "images": [
                    "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "name": "Nourishing Bakuchiol Night Elixir",
                "slug": "nourishing-bakuchiol-night-elixir",
                "sku": "LUM-OIL-002",
                "category": cat_map["facial-oils-essences"],
                "price": Decimal("82.00"),
                "discount_price": Decimal("69.00"),
                "stock_quantity": 140,
                "is_featured": True,
                "sort_order": 8,
                "description": (
                    "Natural 2% retinol alternative derived from Psoralea corylifolia seeds, infused into "
                    "organic evening primrose and blue tansy essential oils. Gently renews cellular texture."
                ),
                "seo_title": "Nourishing Bakuchiol Night Elixir | Penguin Mart",
                "seo_description": "Gentle 2% plant retinol alternative with soothing blue tansy and evening primrose oil.",
                "images": [
                    "https://images.unsplash.com/photo-1608248597359-0010f37f3747?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "name": "Awakening Caffeine & Peptide Eye Balm",
                "slug": "awakening-caffeine-peptide-eye-balm",
                "sku": "LUM-EYE-001",
                "category": cat_map["eye-lip-treatments"],
                "price": Decimal("54.00"),
                "discount_price": Decimal("46.00"),
                "stock_quantity": 380,
                "is_featured": True,
                "sort_order": 9,
                "description": (
                    "Silky under-eye treatment targeting puffiness and dark circles with green coffee extract, "
                    "Argireline peptide, and mica minerals for instant brightening."
                ),
                "seo_title": "Awakening Caffeine & Peptide Eye Balm | Penguin Mart",
                "seo_description": "Green coffee and peptide de-puffing eye balm for visible dark circle reduction.",
                "images": [
                    "https://images.unsplash.com/photo-1512290900672-1f55b9e078c1?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "name": "Overnight Squalane Conditioning Lip Mask",
                "slug": "overnight-squalane-lip-mask",
                "sku": "LUM-LIP-001",
                "category": cat_map["eye-lip-treatments"],
                "price": Decimal("26.00"),
                "discount_price": None,
                "stock_quantity": 600,
                "is_featured": False,
                "sort_order": 10,
                "description": (
                    "Decadent berry and botanical butter conditioning lip treatment with olive squalane, "
                    "mango kernel butter, and vitamin E. Heals cracked dry lips overnight."
                ),
                "seo_title": "Overnight Squalane Conditioning Lip Mask | Penguin Mart",
                "seo_description": "Restorative botanical butter and squalane lip treatment for plump, hydrated lips.",
                "images": [
                    "https://images.unsplash.com/photo-1512290900672-1f55b9e078c1?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "name": "Invisible Mineral Shield SPF 50+",
                "slug": "invisible-mineral-shield-spf50",
                "sku": "LUM-SPF-001",
                "category": cat_map["sunscreen-barrier-shield"],
                "price": Decimal("48.00"),
                "discount_price": Decimal("39.00"),
                "stock_quantity": 720,
                "is_featured": True,
                "sort_order": 11,
                "description": (
                    "Non-nano 18% zinc oxide sunscreen that leaves zero white cast on all skin tones. "
                    "Enriched with centella asiatica, niacinamide, and ectoin for urban pollution shield."
                ),
                "seo_title": "Invisible Mineral Shield SPF 50+ Broad Spectrum | Penguin Mart",
                "seo_description": "Clean non-nano zinc sunscreen SPF 50+ with zero white cast and skin-calming centella.",
                "images": [
                    "https://images.unsplash.com/photo-1598440947619-2c35fc9aa908?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "name": "Centella Asiatica Calming Barrier Sun Gel",
                "slug": "centella-calming-sun-gel",
                "sku": "LUM-SPF-002",
                "category": cat_map["sunscreen-barrier-shield"],
                "price": Decimal("44.00"),
                "discount_price": None,
                "stock_quantity": 310,
                "is_featured": False,
                "sort_order": 12,
                "description": (
                    "Refreshing water-burst sunscreen lotion with 49% organic Centella Asiatica leaf water. "
                    "Instantly cools sensitized skin while providing photostable daily UV defense."
                ),
                "seo_title": "Centella Asiatica Calming Barrier Sun Gel SPF 50 | Penguin Mart",
                "seo_description": "Cooling soothing centella sunscreen lotion designed for sensitive and blemish-prone skin.",
                "images": [
                    "https://images.unsplash.com/photo-1598440947619-2c35fc9aa908?auto=format&fit=crop&w=800&q=80",
                ],
            },
        ]

        seeded_products = []
        for pdata in products_data:
            images = pdata.pop("images")
            prod, _ = Product.objects.update_or_create(
                slug=pdata["slug"],
                defaults={
                    "name": pdata["name"],
                    "sku": pdata["sku"],
                    "category": pdata["category"],
                    "price": pdata["price"],
                    "discount_price": pdata["discount_price"],
                    "stock_quantity": pdata["stock_quantity"],
                    "status": Product.STATUS_ACTIVE,
                    "is_visible": True,
                    "is_featured": pdata["is_featured"],
                    "sort_order": pdata["sort_order"],
                    "description": pdata["description"],
                    "seo_title": pdata["seo_title"],
                    "seo_description": pdata["seo_description"],
                },
            )
            # Recreate images cleanly
            prod.images.all().delete()
            for idx, img_url in enumerate(images):
                ProductImage.objects.create(
                    product=prod,
                    image_url=img_url,
                    alt_text=f"{prod.name} showcase",
                    sort_order=idx + 1,
                    is_primary=(idx == 0),
                )
            seeded_products.append(prod)
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(seeded_products)} active products with images."))

        # 5. Campaigns
        campaigns = [
            {
                "name": "Spring Botanical Radiance 2026",
                "slug": "spring-radiance-2026",
                "description": "Seasonal editorial highlighting bio-fermented flower mists and cold-pressed facial oils.",
                "badge_text": "Spring Feature",
                "status": Campaign.STATUS_ACTIVE,
            },
            {
                "name": "Wholesale Starter Restock",
                "slug": "wholesale-starter-restock",
                "description": "Special tier program for salon and spa owners ordering introductory assortment bundles.",
                "badge_text": "Wholesale Tier",
                "status": Campaign.STATUS_ACTIVE,
            },
        ]
        camp_map = {}
        for cdata in campaigns:
            camp, _ = Campaign.objects.update_or_create(
                slug=cdata["slug"],
                defaults=cdata,
            )
            camp_map[cdata["slug"]] = camp
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(campaigns)} marketing campaigns."))

        # 6. Content Blocks
        content_blocks = [
            {
                "content_type": ContentBlock.TYPE_HERO,
                "slug": "spring-botanical-hero",
                "title": "Pure Botanical Science for Modern Skincare",
                "body": (
                    "Lumera delivers high-potency wholesale skincare engineered for aesthetic clinics, "
                    "luxury day spas, and discerning beauty retailers worldwide. Clean, certified, and cruelty-free."
                ),
                "cta_label": "Explore Wholesale Catalog",
                "cta_url": "/products",
                "alt_text": "Spring 2026 Botanical Collection",
                "image_url": "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=1200&q=80",
                "campaign": camp_map.get("spring-radiance-2026"),
                "status": ContentBlock.STATUS_PUBLISHED,
                "sort_order": 1,
            },
            {
                "content_type": ContentBlock.TYPE_ANNOUNCEMENT,
                "slug": "spring-restock-announcement",
                "title": "Wholesale Restock Promo",
                "body": "✨ Spring Wholesale Event: Enjoy tiered discounts up to 25% on volume orders over $500.",
                "cta_label": "View Tier Pricing",
                "cta_url": "/products",
                "alt_text": "Limited Time Wholesale Promo",
                "image_url": "",
                "campaign": camp_map.get("wholesale-starter-restock"),
                "status": ContentBlock.STATUS_PUBLISHED,
                "sort_order": 2,
            },
            {
                "content_type": ContentBlock.TYPE_PROMO_SECTION,
                "slug": "clinical-botany-promo",
                "title": "Formulated for Cellular Barrier Integrity",
                "body": (
                    "Every formulation is backed by independent third-party clinical efficacy testing. "
                    "Experience high-tolerance restorative botanicals with guaranteed minimum 24-month shelf life."
                ),
                "cta_label": "Discover Formulations",
                "cta_url": "/products",
                "alt_text": "Clean Science Barrier Protection",
                "image_url": "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=1200&q=80",
                "campaign": camp_map.get("spring-radiance-2026"),
                "status": ContentBlock.STATUS_PUBLISHED,
                "sort_order": 3,
            },
        ]

        for bdata in content_blocks:
            ContentBlock.objects.update_or_create(
                slug=bdata["slug"],
                defaults=bdata,
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(content_blocks)} active content blocks."))

        # 7. Demo Customer Orders
        prod1 = seeded_products[0]  # Mist ($32.00)
        prod2 = seeded_products[2]  # Oil ($65.00)
        prod3 = seeded_products[5]  # Cream ($62.00)

        # Order 1: Delivered
        order1, created1 = Order.objects.update_or_create(
            order_number="LUM-2026-1001",
            defaults={
                "user": customer_user,
                "status": Order.STATUS_DELIVERED,
                "payment_status": Order.PAYMENT_PAID,
                "currency": "USD",
                "subtotal": Decimal("159.00"),
                "shipping_cost": Decimal("0.00"),
                "discount_total": Decimal("15.00"),
                "total": Decimal("144.00"),
                "shipping_full_name": "Sophia Laurent",
                "shipping_phone": "+1-555-019-2834",
                "shipping_address_line1": "742 Evergreen Botanical Way, Suite 4B",
                "shipping_city": "San Francisco",
                "shipping_area": "Bay Area",
                "shipping_postal_code": "94107",
                "shipping_country": "United States",
                "customer_notes": "Please leave package with front concierge.",
                "courier": "FedEx Express Skincare Priority",
                "tracking_number": "FDX-8392019482",
                "tracking_url": "https://www.fedex.com/tracking?id=FDX-8392019482",
                "shipped_at": timezone.now() - timezone.timedelta(days=7),
                "delivered_at": timezone.now() - timezone.timedelta(days=4),
            },
        )
        if created1 or order1.items.count() == 0:
            order1.items.all().delete()
            OrderItem.objects.create(
                order=order1,
                product=prod1,
                product_name=prod1.name,
                product_sku=prod1.sku,
                product_image=prod1.primary_image or "",
                unit_price=Decimal("32.00"),
                quantity=2,
                line_total=Decimal("64.00"),
            )
            OrderItem.objects.create(
                order=order1,
                product=prod2,
                product_name=prod2.name,
                product_sku=prod2.sku,
                product_image=prod2.primary_image or "",
                unit_price=Decimal("65.00"),
                quantity=1,
                line_total=Decimal("65.00"),
            )
            OrderItem.objects.create(
                order=order1,
                product=prod3,
                product_name=prod3.name,
                product_sku=prod3.sku,
                product_image=prod3.primary_image or "",
                unit_price=Decimal("62.00"),
                quantity=1,
                line_total=Decimal("62.00"),
            )
            OrderStatusHistory.objects.create(
                order=order1,
                from_status="",
                to_status=Order.STATUS_PENDING,
                changed_by=customer_user,
            )
            OrderStatusHistory.objects.create(
                order=order1,
                from_status=Order.STATUS_PENDING,
                to_status=Order.STATUS_CONFIRMED,
                changed_by=staff_user,
            )
            OrderStatusHistory.objects.create(
                order=order1,
                from_status=Order.STATUS_CONFIRMED,
                to_status=Order.STATUS_SHIPPED,
                changed_by=staff_user,
            )
            OrderStatusHistory.objects.create(
                order=order1,
                from_status=Order.STATUS_SHIPPED,
                to_status=Order.STATUS_DELIVERED,
                changed_by=staff_user,
            )

        # Order 2: Shipped (in transit)
        order2, created2 = Order.objects.update_or_create(
            order_number="LUM-2026-1002",
            defaults={
                "user": customer_user,
                "status": Order.STATUS_SHIPPED,
                "payment_status": Order.PAYMENT_PAID,
                "currency": "USD",
                "subtotal": Decimal("220.00"),
                "shipping_cost": Decimal("15.00"),
                "discount_total": Decimal("0.00"),
                "total": Decimal("235.00"),
                "shipping_full_name": "Sophia Laurent",
                "shipping_phone": "+1-555-019-2834",
                "shipping_address_line1": "742 Evergreen Botanical Way, Suite 4B",
                "shipping_city": "San Francisco",
                "shipping_area": "Bay Area",
                "shipping_postal_code": "94107",
                "shipping_country": "United States",
                "customer_notes": "Handle with care - glass dropper bottles.",
                "courier": "DHL Eco Delivery",
                "tracking_number": "DHL-7719283401",
                "tracking_url": "https://www.dhl.com/tracking?id=DHL-7719283401",
                "shipped_at": timezone.now() - timezone.timedelta(days=1),
            },
        )
        if created2 or order2.items.count() == 0:
            order2.items.all().delete()
            OrderItem.objects.create(
                order=order2,
                product=prod2,
                product_name=prod2.name,
                product_sku=prod2.sku,
                product_image=prod2.primary_image or "",
                unit_price=Decimal("65.00"),
                quantity=2,
                line_total=Decimal("130.00"),
            )
            OrderItem.objects.create(
                order=order2,
                product=prod3,
                product_name=prod3.name,
                product_sku=prod3.sku,
                product_image=prod3.primary_image or "",
                unit_price=Decimal("62.00"),
                quantity=1,
                line_total=Decimal("62.00"),
            )
            OrderStatusHistory.objects.create(
                order=order2,
                from_status="",
                to_status=Order.STATUS_PENDING,
                changed_by=customer_user,
            )
            OrderStatusHistory.objects.create(
                order=order2,
                from_status=Order.STATUS_PENDING,
                to_status=Order.STATUS_CONFIRMED,
                changed_by=staff_user,
            )
            OrderStatusHistory.objects.create(
                order=order2,
                from_status=Order.STATUS_CONFIRMED,
                to_status=Order.STATUS_SHIPPED,
                changed_by=staff_user,
            )

        self.stdout.write(self.style.SUCCESS("Seeded 2 demo orders with historical items and tracking."))
        self.stdout.write(self.style.SUCCESS("=== LUMERA DEMO DATA SEEDING COMPLETE ==="))
