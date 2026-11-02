"""
Starting content for the member directory and the shop, called from
`python manage.py seed_content`. Idempotent: rows that already exist are
left exactly as the admins edited them.

Founding members come from the About text and the governance document.
Fields we do not know yet (logos, Instagram pages, regions of some groups)
are left blank for the secretariat to fill in the admin panel.
"""

from django.contrib.auth.models import Group, Permission

from home.management.commands import seed_data

from .models import DirectorySettings, Member, MemberIndexPage, Region

MEMBERS_PAGE = {
    "fa": {
        "title": "اعضا",
        "slug": "members",
        "intro": "<p>تولیدکنندگان، نهادها و حامیانی که به اصول ده‌گانه تجارت عادلانه پایبندند و عضو خانه تجارت عادلانه ایران هستند.</p>",
    },
    "en": {
        "title": "Members",
        "slug": "members",
        "intro": "<p>The producers, organisations and supporters who are committed to the ten principles of fair trade and belong to the Fair Trade House of Iran.</p>",
    },
}

SHOP_PAGE = {
    "fa": {
        "title": "فروشگاه",
        "slug": "shop",
        "intro": "<p>محصولات تولیدکنندگان عضو خانه؛ ساخته‌شده با دستمزد منصفانه و احترام به انسان و طبیعت.</p>",
    },
    "en": {
        "title": "Shop",
        "slug": "shop",
        "intro": "<p>Products made by member producers, with fair pay and respect for people and nature.</p>",
    },
}

# (Persian, English) — the 31 provinces, so admins can pick a region from a list.
REGIONS = [
    ("آذربایجان شرقی", "East Azerbaijan"), ("آذربایجان غربی", "West Azerbaijan"), ("اردبیل", "Ardabil"),
    ("اصفهان", "Isfahan"), ("البرز", "Alborz"), ("ایلام", "Ilam"), ("بوشهر", "Bushehr"), ("تهران", "Tehran"),
    ("چهارمحال و بختیاری", "Chaharmahal and Bakhtiari"), ("خراسان جنوبی", "South Khorasan"),
    ("خراسان رضوی", "Razavi Khorasan"), ("خراسان شمالی", "North Khorasan"), ("خوزستان", "Khuzestan"),
    ("زنجان", "Zanjan"), ("سمنان", "Semnan"), ("سیستان و بلوچستان", "Sistan and Baluchestan"), ("فارس", "Fars"),
    ("قزوین", "Qazvin"), ("قم", "Qom"), ("کردستان", "Kurdistan"), ("کرمان", "Kerman"), ("کرمانشاه", "Kermanshah"),
    ("کهگیلویه و بویراحمد", "Kohgiluyeh and Boyer-Ahmad"), ("گلستان", "Golestan"), ("گیلان", "Gilan"),
    ("لرستان", "Lorestan"), ("مازندران", "Mazandaran"), ("مرکزی", "Markazi"), ("هرمزگان", "Hormozgan"),
    ("همدان", "Hamadan"), ("یزد", "Yazd"),
]

CATEGORIES = [
    ("زیورآلات", "Jewellery", "jewellery"),
    ("صنایع دستی", "Handicrafts", "handicrafts"),
    ("پوشاک و منسوجات", "Textiles and clothing", "textiles"),
    ("خوراکی‌های بومی", "Local food products", "food"),
    ("خانه و دکور", "Home and decor", "home-decor"),
]

FOUNDING_MEMBERS = [
    {
        "slug": "armoz", "name": "ارموز", "name_en": "Armoz", "member_type": Member.PRODUCER,
        "region": "هرمزگان", "city": "میناب", "city_en": "Minab",
        "summary": "فرآورده‌های بومی میناب", "summary_en": "Native products of Minab",
    },
    {
        "slug": "papital", "name": "پاپیتال", "name_en": "Papital", "member_type": Member.PRODUCER,
        "summary": "گروه زیورآلات پاپیتال", "summary_en": "Papital jewellery group",
    },
    {
        "slug": "parvand-boom", "name": "پروندبوم", "name_en": "Parvand Boom", "member_type": Member.PRODUCER,
        "region": "فارس",
        "summary": "محصولات بومی جنوب فارس", "summary_en": "Native products of southern Fars",
    },
    {
        "slug": "tida", "name": "تیدا", "name_en": "Tida", "member_type": Member.PRODUCER,
        "summary": "صنایع دستی زنان ترکمن", "summary_en": "Handicrafts by Turkmen women",
    },
    {
        "slug": "chagerd", "name": "چاگرد", "name_en": "Chagerd", "member_type": Member.PRODUCER,
        "summary": "محصولات زنان بلوچ", "summary_en": "Products by Baluch women",
    },
    {
        "slug": "lena", "name": "لنا", "name_en": "Lena", "member_type": Member.PRODUCER,
        "region": "کرمان",
        "summary": "صنایع دستی زنان کرمان", "summary_en": "Handicrafts by Kerman women",
    },
    {
        "slug": "mehrbaf", "name": "مهرباف", "name_en": "Mehrbaf", "member_type": Member.PRODUCER,
        "summary": "گروه توان‌افزایی زنان", "summary_en": "Women's empowerment group",
    },
    {
        "slug": "women-youth-entrepreneurship-foundation",
        "name": "بنیاد توسعه کارآفرینی زنان و جوانان",
        "name_en": "Women and Youth Entrepreneurship Development Foundation",
        "member_type": Member.INSTITUTION,
        "summary": "توانمندسازی کسب‌وکارهای زنان و جوانان",
        "summary_en": "Capacity building for women- and youth-led businesses",
    },
    {
        "slug": "haft-dast", "name": "خانه شتاب‌دهنده صنایع دستی هفت دست",
        "name_en": "Haft Dast Handicrafts Accelerator", "member_type": Member.INSTITUTION,
        "summary": "شتاب‌دهنده کسب‌وکارهای صنایع دستی و از بنیان‌گذاران خانه تجارت عادلانه",
        "summary_en": "Handicrafts business accelerator and co-founder of the house",
    },
]

# Groups that may add and edit members, products, categories and regions in the admin panel.
EDITOR_GROUPS = [seed_data.SECRETARIAT, seed_data.PR]
EDIT_MODELS = [("members", "member"), ("members", "region"), ("products", "product"),
               ("products", "category"), ("products", "productimage")]
SETTINGS_MODELS = [("members", "directorysettings"), ("products", "shopsettings")]


def seed_directory(command, home_fa, home_en):
    """Called by seed_content with its Command instance (for ensure_page and stdout)."""
    from products.models import Category, ProductIndexPage, ShopSettings

    command.ensure_page(home_fa, home_en, MemberIndexPage, MEMBERS_PAGE, order_hint="members")
    command.ensure_page(home_fa, home_en, ProductIndexPage, SHOP_PAGE, order_hint="shop")

    for order, (name, name_en) in enumerate(REGIONS):
        Region.objects.get_or_create(name=name, defaults={"name_en": name_en, "sort_order": order})

    for order, (name, name_en, slug) in enumerate(CATEGORIES):
        if not Category.objects.filter(slug=slug).exists() and not Category.objects.filter(name=name).exists():
            Category.objects.create(name=name, name_en=name_en, slug=slug, sort_order=order)

    created = 0
    for order, row in enumerate(FOUNDING_MEMBERS):
        if Member.objects.filter(slug=row["slug"]).exists():
            continue
        fields = dict(row)
        region = fields.pop("region", None)
        Member.objects.create(
            status=Member.OFFICIAL, is_founding=True, is_featured=True, sort_order=order + 1,
            region=Region.objects.filter(name=region).first() if region else None,
            **fields,
        )
        created += 1
    if created:
        command.stdout.write(f"Created {created} founding members")

    DirectorySettings.load()
    ShopSettings.load()
    _grant_permissions()


def _grant_permissions():
    perms = []
    for app_label, model in EDIT_MODELS:
        for action in ("add", "change", "delete"):
            perms.append(Permission.objects.get(content_type__app_label=app_label, codename=f"{action}_{model}"))
    for app_label, model in SETTINGS_MODELS:
        perms.append(Permission.objects.get(content_type__app_label=app_label, codename=f"change_{model}"))
    for name in EDITOR_GROUPS:
        group = Group.objects.filter(name=name).first()
        if group:
            group.permissions.add(*perms)
