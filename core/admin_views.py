"""
Admin pages of our own: the shortcuts on the dashboard and the Persian guide
(«راهنمای پنل», /admin/guide/). Registered by core/wagtail_hooks.py.

Each shortcut and each part of the guide is shown only to people whose group
can use it, so a PR volunteer sees pages and pictures, the secretariat sees
membership files, and so on.
"""

from django.template.response import TemplateResponse
from django.urls import reverse


def _count(queryset):
    try:
        return queryset.count()
    except Exception:  # a count must never break the dashboard
        return 0


def can_edit_pages(user):
    from wagtail.admin.auth import user_has_any_page_permission

    return user_has_any_page_permission(user)


def can_upload(user):
    from wagtail.documents.permissions import permission_policy as documents
    from wagtail.images.permissions import permission_policy as images

    return images.user_has_permission(user, "add"), documents.user_has_permission(user, "add")


def news_index_for(user):
    """The Persian news section, if the user may add news to it."""
    from wagtail.models import Locale

    from news.models import NewsIndexPage

    index = NewsIndexPage.objects.filter(locale=Locale.get_default()).first()
    if index and index.permissions_for_user(user).can_add_subpage():
        return index
    return None


def pending_for(user):
    """
    «کارهای منتظر شما» at the top of the dashboard: one line per kind of waiting work the user
    can act on, with how many and a link to that filtered list. Empty when nothing waits.
    """
    from django.utils import timezone

    from appeals.models import Appeal
    from contact.models import Complaint
    from members.models import Member
    from membership.admin_views import VIEW_PERM, files_needing_action
    from products.models import Product
    from shop.admin_views import FILTERS as ORDER_FILTERS, can_manage
    from shop.models import Order
    from standing.models import Dues, DuesPayment
    from standing.services import COMMISSION, SECRETARIAT, user_bodies
    from wholesale.models import WholesaleInquiry

    items = []

    def add(count, label, url):
        if count:
            items.append({"count": count, "label": label, "url": url})

    if user.has_perm(VIEW_PERM):
        add(_count(files_needing_action(user)), "پرونده عضویت منتظر اقدام شما",
            reverse("membership_applications:index") + "?status=mine")
    bodies = user_bodies(user)
    today = timezone.localdate()
    standing = reverse("standing:index")
    if SECRETARIAT in bodies:
        add(_count(DuesPayment.objects.filter(status=DuesPayment.Status.PENDING)),
            "رسید حق عضویت منتظر بررسی", standing + "?show=pending")
        add(_count(Dues.objects.filter(status=Dues.Status.UNPAID, due_date__lt=today)),
            "حق عضویت گذشته از مهلت", standing + "?show=overdue")
    if bodies & {SECRETARIAT, COMMISSION}:
        add(_count(Member.objects.filter(status=Member.SUSPENDED, suspended_until__lte=today)),
            "عضو با مدت تعلیق تمام‌شده (رفع تعلیق یا لغو)", standing + "?show=ended")
    if can_manage(user):
        orders = reverse("shop_orders:index")
        conditions = {key: condition for key, _, condition in ORDER_FILTERS}
        for key, label in (("todo", "رسید پرداخت سفارش منتظر بررسی"), ("ship", "سفارش پرداخت‌شده منتظر ارسال"),
                           ("returns", "درخواست مرجوعی بررسی‌نشده"), ("settle", "سفارش تسویه‌نشده با تولیدکننده")):
            add(_count(Order.objects.filter(conditions[key])), label, f"{orders}?show={key}")
    if user.has_perm("products.change_product"):
        add(_count(Product.objects.filter(needs_review=True)), "محصول تازهٔ اعضا منتظر بررسی",
            reverse("wagtailsnippets_products_product:list") + "?needs_review=true")
    if user.has_perm("wholesale.change_wholesaleinquiry"):
        add(_count(WholesaleInquiry.objects.filter(status=WholesaleInquiry.Status.NEW)),
            "درخواست خرید عمدهٔ تازه", reverse("wholesale_inquiries:index"))
    if user.has_perm("contact.change_complaint"):
        add(_count(Complaint.objects.filter(status=Complaint.Status.RECEIVED)), "شکایت تازه",
            reverse("complaints:index"))
    if user.has_perm("appeals.change_appeal"):
        add(_count(Appeal.objects.filter(status=Appeal.Status.RECEIVED)), "اعتراض تازه", reverse("appeals:index"))
    return items


def shortcuts_for(user):
    """
    The dashboard tiles: the few things each person starts most often, only those the user can
    use (a PR volunteer sees four, the secretariat two or three). Waiting work is counted in
    «کارهای منتظر شما» above them, and everything else is in the menu.
    """
    from membership.admin_views import VIEW_PERM
    from shop.admin_views import can_manage
    from standing.services import can_view as can_view_standing

    tiles = []

    def add(label, url, icon, hint=""):
        tiles.append({"label": label, "url": url, "icon": icon, "hint": hint})

    news_index = news_index_for(user)
    if news_index:
        add("نوشتن خبر یا رویداد", reverse("wagtailadmin_pages:add", args=("news", "newspage", news_index.pk)),
            "edit", "در بخش «{}»".format(news_index.title))
    if can_edit_pages(user):
        add("صفحه‌های سایت", reverse("wagtailadmin_explore_root"), "folder-open-inverse",
            "ویرایش متن صفحه‌ها، فارسی و انگلیسی")
    images, documents = can_upload(user)
    if images:
        add("بارگذاری عکس", reverse("wagtailimages:add_multiple"), "image", "چند عکس با هم")
    if documents:
        add("بارگذاری سند", reverse("wagtaildocs:add_multiple"), "doc-full-inverse", "گزارش، صورت‌جلسه، اساسنامه، …")
    if user.has_perm(VIEW_PERM):
        add("پرونده‌های عضویت", reverse("membership_applications:index"), "group", "درخواست‌ها و مهلت‌ها")
    if can_view_standing(user):
        add("وضعیت اعضا و حق عضویت", reverse("standing:index"), "user", "رسیدها، بدهی، تعلیق")
    if can_manage(user):
        add("سفارش‌های فروشگاه", reverse("shop_orders:index"), "clipboard-list", "رسیدها، ارسال، تسویه")
    if user.has_perm("core.change_sitesettings"):
        add("تنظیمات سایت", reverse("wagtailsettings:edit", args=("core", "sitesettings")), "cogs",
            "لوگو، نام، راه‌های تماس، شبکه‌های اجتماعی")
    return tiles


def _collections():
    """Document collections and who may open their files, as the guide lists them."""
    from wagtail.models import Collection, CollectionViewRestriction

    rows = []
    for collection in Collection.objects.filter(depth__gt=1).order_by("path"):
        restrictions = list(collection.get_view_restrictions())
        if not restrictions:
            who = "همه (عمومی)"
        else:
            parts = []
            for r in restrictions:
                if r.restriction_type == CollectionViewRestriction.GROUPS:
                    parts.append("، ".join(g.name for g in r.groups.all()))
                elif r.restriction_type == CollectionViewRestriction.LOGIN:
                    parts.append("هر کسی که وارد شده باشد")
                else:
                    parts.append("با رمز")
            who = "؛ ".join(p for p in parts if p) or "محدود"
        rows.append({"name": collection.name, "who": who, "public": not restrictions})
    return rows


def guide(request):
    from wagtail.models import Locale, Page

    from core.models import MembershipSettings
    from membership.admin_views import VIEW_PERM
    from shop.admin_views import can_manage
    from standing.services import can_view as can_view_standing

    user = request.user
    images, documents = can_upload(user)
    # The approval workflow of the Persian home page (seed_content sets «تأیید انتشار محتوا»).
    home = Page.objects.filter(depth=2, locale=Locale.get_default()).first()
    workflow = home.get_workflow() if home else None
    sections = {
        "pages": can_edit_pages(user),
        "media": images or documents,
        "membership": user.has_perm(VIEW_PERM) or can_view_standing(user),
        "orders": can_manage(user),
        "wholesale": user.has_perm("wholesale.change_wholesaleinquiry"),
        "products": user.has_perm("products.change_product"),
        "settings": user.has_perm("core.change_sitesettings") or user.has_perm("core.change_membershipsettings"),
        "users": user.has_perm("auth.add_user") or user.is_superuser,
    }
    sections["shop"] = sections["orders"] or sections["wholesale"] or sections["products"]
    return TemplateResponse(request, "core/admin/guide.html", {
        "page_title": "راهنمای پنل مدیریت",
        "header_title": "راهنمای پنل مدیریت",
        "header_icon": "help",
        "show": sections,
        "workflow_name": workflow.name if workflow else "",
        "collections": _collections() if sections["media"] else [],
        "membership_settings": MembershipSettings.load(request_or_site=request) if sections["membership"] else None,
        "news_index": news_index_for(user),
    })
