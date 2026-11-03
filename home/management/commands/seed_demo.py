"""
Demo content for a test copy of the site (deploy/local/run-demo.sh, guide docs/demo-fa.md).

Runs seed_content, then adds sample products with placeholder pictures,
sample membership applications, demo logins, and turns on the test
payment gateway and noindex. Never run it on the real site: the command
refuses unless DEMO_MODE=1 or DEBUG is on.

    DEMO_PASSWORD=... python manage.py seed_demo

Idempotent: existing rows are left alone, but the demo users' passwords
are reset to DEMO_PASSWORD on every run. With --passwords-only it does
just that.
"""

import io
import os
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.images import ImageFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image as PILImage, ImageDraw
from wagtail.images.models import Image

from core.models import SeoSettings
from members.models import Member
from membership.models import MembershipApplication, Status
from payments.models import PaymentSettings
from products.models import Category, Product, ProductImage, ShopSettings
from shop.models import Seller

from . import seed_data as data

# (member slug, category slug, fa name, en name, fa summary, en summary, price in rial, colour, featured)
PRODUCTS = [
    ("armoz", "food", "رب انار میناب", "Minab pomegranate paste", "رب انار خانگی بدون افزودنی",
     "Home-made pomegranate paste, no additives", 2_400_000, "#873319", True),
    ("armoz", "food", "خرمای مضافتی", "Mazafati dates", "خرمای تازه هرمزگان، بسته یک کیلویی",
     "Fresh dates from Hormozgan, 1 kg box", 1_850_000, "#5b3a1e", False),
    ("papital", "jewellery", "گردنبند نقره دست‌ساز", "Handmade silver necklace", "نقره و سنگ فیروزه",
     "Silver with turquoise", 9_500_000, "#1a1c46", True),
    ("papital", "jewellery", "گوشواره پته", "Pateh earrings", "گوشواره با سوزن‌دوزی پته کرمان",
     "Earrings with Kerman pateh embroidery", 3_200_000, "#cf9d2b", False),
    ("tida", "textiles", "شال ابریشمی ترکمن", "Turkmen silk shawl", "بافت دست زنان ترکمن",
     "Hand-woven by Turkmen women", 12_000_000, "#a03030", True),
    ("chagerd", "handicrafts", "کیف سوزن‌دوزی بلوچ", "Baluch embroidered bag", "سوزن‌دوزی سنتی بلوچستان",
     "Traditional Baluch needlework", 6_800_000, "#2e6b5e", True),
    ("lena", "handicrafts", "رومیزی پته", "Pateh table runner", "سوزن‌دوزی پته روی پارچه پشمی",
     "Pateh needlework on wool", 7_400_000, "#7a2e4a", False),
    ("mehrbaf", "home-decor", "کوسن گلیم‌بافت", "Kilim cushion", "روکش کوسن با بافت گلیم",
     "Kilim-woven cushion cover", 4_500_000, "#a87d1c", True),
    ("parvand-boom", "food", "عسل کوهی", "Mountain honey", "عسل طبیعی کوه‌های جنوب فارس",
     "Natural honey from the mountains of southern Fars", 5_200_000, "#d9a21b", False),
]

# Which demo producers sell through the site's cart, and how.
SELLERS = {
    "armoz": Seller.Mode.HOUSE, "papital": Seller.Mode.HOUSE, "tida": Seller.Mode.HOUSE,
    "chagerd": Seller.Mode.HOUSE, "mehrbaf": Seller.Mode.HOUSE,
}

APPLICATIONS = [
    {"name": "گروه بافندگان نمونه", "name_en": "Sample Weavers Group", "member_type": "producer",
     "contact_person": "متقاضی نمونه یک", "city": "یزد", "status": Status.SUBMITTED, "days_left": 7},
    {"name": "انجمن حامیان نمونه", "name_en": "Sample Supporters Association", "member_type": "institution",
     "contact_person": "متقاضی نمونه دو", "city": "تهران", "status": Status.COMMISSION, "days_left": 25},
    {"name": "کارگاه سفال نمونه", "name_en": "Sample Pottery Workshop", "member_type": "producer",
     "contact_person": "متقاضی نمونه سه", "city": "اصفهان", "status": Status.TRIAL, "days_left": 80},
]

# username, staff?, superuser?, groups, member slug managed in the panel
USERS = [
    ("demo-admin", True, True, [], None),
    ("demo-secretariat", True, False, [data.SECRETARIAT], None),
    ("demo-member", False, False, [data.MEMBERS_GROUP], "armoz"),
]


def placeholder_picture(colour, seed):
    """A plain square picture in the product's colour with a simple pattern, as JPEG bytes."""
    img = PILImage.new("RGB", (800, 800), colour)
    draw = ImageDraw.Draw(img)
    for i in range(6):
        r = 90 + i * 55 + seed * 7
        draw.ellipse((400 - r, 400 - r, 400 + r, 400 + r), outline=(255, 255, 255), width=6)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    buf.seek(0)
    return buf


class Command(BaseCommand):
    help = "Load demo content for a test copy of the site (needs DEMO_MODE=1 or DEBUG)."

    def add_arguments(self, parser):
        parser.add_argument("--passwords-only", action="store_true",
                            help="Only set the demo users' passwords (fast; for each start of a pre-built demo image).")

    def handle(self, *args, **options):
        if not (settings.DEMO_MODE or settings.DEBUG):
            raise CommandError("seed_demo only runs with DEMO_MODE=1 (or DEBUG). Never on the real site.")
        password = os.environ.get("DEMO_PASSWORD", "")
        if len(password) < 8:
            raise CommandError("Set DEMO_PASSWORD (at least 8 characters) for the demo logins.")

        if options["passwords_only"]:
            self.ensure_users(password)
            self.stdout.write(self.style.SUCCESS("Demo passwords set."))
            return

        call_command("seed_content", stdout=self.stdout)
        with transaction.atomic():
            self.ensure_settings()
            self.ensure_products()
            self.ensure_applications()
            self.ensure_users(password)
        self.stdout.write(self.style.SUCCESS("Demo content is in place."))

    def ensure_settings(self):
        seo = SeoSettings.load()
        seo.allow_indexing = False
        seo.save()

        pay = PaymentSettings.load()
        pay.enabled = True
        pay.provider = PaymentSettings.Provider.TEST
        pay.save()

        shop = ShopSettings.load()
        shop.cart_enabled = True
        shop.cart_enabled_en = True
        shop.save()

    def ensure_products(self):
        for i, (member_slug, cat, name, name_en, summary, summary_en, price, colour, featured) in enumerate(PRODUCTS):
            if Product.objects.filter(name=name).exists():
                continue
            member = Member.objects.filter(slug=member_slug).first()
            if member is None:
                continue
            product = Product.objects.create(
                member=member, category=Category.objects.filter(slug=cat).first(),
                name=name, name_en=name_en, summary=summary, summary_en=summary_en,
                description=f"<p>{summary}. این محصول نمونه است و فقط برای آزمودن سایت ساخته شده.</p>",
                description_en=f"<p>{summary_en}. A sample product, made only for testing the site.</p>",
                price=price, stock_quantity=20, is_featured=featured, sort_order=i + 1,
            )
            image = Image(title=f"نمونه - {name}",
                          file=ImageFile(placeholder_picture(colour, i), name=f"demo-product-{i + 1}.jpg"))
            image.save()
            ProductImage.objects.create(product=product, image=image, sort_order=0)
        for slug, mode in SELLERS.items():
            member = Member.objects.filter(slug=slug).first()
            if member and not Seller.objects.filter(member=member).exists():
                Seller.objects.create(member=member, mode=mode, shipping_fee=500_000, prep_days=3,
                                      shipping_note="ارسال با پست پیشتاز", shipping_note_en="Sent by express post")

    def ensure_applications(self):
        today = date.today()
        for row in APPLICATIONS:
            if MembershipApplication.objects.filter(name=row["name"]).exists():
                continue
            row = dict(row)
            days_left = row.pop("days_left")
            extra = {}
            if row["status"] == Status.TRIAL:
                extra = {"trial_starts_on": today - timedelta(days=10), "trial_ends_on": today + timedelta(days=80)}
            MembershipApplication.objects.create(
                email="applicant@example.com", phone="09120000000", deadline=today + timedelta(days=days_left),
                agreed_principles=True, agreed_inspections=True, **row, **extra,
            )

    def ensure_users(self, password):
        User = get_user_model()
        for username, staff, superuser, groups, member_slug in USERS:
            user, _ = User.objects.get_or_create(username=username,
                                                 defaults={"email": f"{username}@example.com"})
            user.is_staff = staff
            user.is_superuser = superuser
            user.set_password(password)
            user.save()
            for name in groups:
                group = Group.objects.filter(name=name).first()
                if group:
                    user.groups.add(group)
            if member_slug:
                member = Member.objects.filter(slug=member_slug).first()
                if member:
                    member.managers.add(user)
