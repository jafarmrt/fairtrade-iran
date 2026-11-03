from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.ui.tables import BooleanColumn, Column
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from memberpanel.models import LoginMobile

from .models import Member, Region


class MemberFilterSet(WagtailFilterSet):
    class Meta:
        model = Member
        fields = ["member_type", "status", "is_founding", "region", "is_published", "is_featured"]


class MemberViewSet(SnippetViewSet):
    model = Member
    icon = "group"
    menu_label = "پروفایل اعضا"
    list_display = [
        "name", "name_en",
        Column("get_member_type_display", label="نوع عضویت", sort_key="member_type"),
        Column("get_status_display", label="وضعیت عضویت", sort_key="status"),
        "region",
        BooleanColumn("is_founding", label="عضو مؤسس"),
        BooleanColumn("is_published", label="نمایش در سایت"),
    ]
    list_export = ["name", "name_en", "member_type", "status", "region", "city", "is_founding",
                   "joined_on", "instagram_url", "website_url", "public_phone", "public_email"]
    filterset_class = MemberFilterSet
    search_fields = ["name", "name_en", "summary"]
    ordering = ["sort_order", "name"]


class RegionViewSet(SnippetViewSet):
    model = Region
    icon = "site"
    menu_label = "مناطق"
    list_display = ["name", "name_en", "sort_order"]


class LoginMobileViewSet(SnippetViewSet):
    model = LoginMobile
    icon = "mobile-alt"
    menu_label = "شماره‌های موبایل ورود"
    list_display = ["user", "mobile", Column("verified_at", label="تأیید با کد")]
    search_fields = ["mobile", "user__username", "user__email"]


class DirectoryGroup(SnippetViewSetGroup):
    """«اعضا» in the admin menu. Products and categories are in «فروشگاه» (shop/wagtail_hooks.py)."""

    items = (MemberViewSet, RegionViewSet, LoginMobileViewSet)
    menu_icon = "group"
    menu_label = "اعضا"
    menu_name = "directory"  # the order of the main menu is set in core/wagtail_hooks.py


register_snippet(DirectoryGroup)
