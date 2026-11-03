from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.ui.tables import BooleanColumn, Column
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from products.models import Category, Product

from .models import Member, Region


class MemberFilterSet(WagtailFilterSet):
    class Meta:
        model = Member
        fields = ["member_type", "status", "is_founding", "region", "is_published", "is_featured"]


class MemberViewSet(SnippetViewSet):
    model = Member
    icon = "group"
    menu_label = "اعضا"
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


class ProductFilterSet(WagtailFilterSet):
    class Meta:
        model = Product
        fields = ["member", "category", "in_stock", "is_published", "is_featured"]


class ProductViewSet(SnippetViewSet):
    model = Product
    icon = "pick"
    menu_label = "محصولات"
    list_display = [
        "name", "name_en", "member", "category", "price",
        BooleanColumn("in_stock", label="موجود است"),
        BooleanColumn("is_published", label="نمایش در سایت"),
    ]
    filterset_class = ProductFilterSet
    search_fields = ["name", "name_en", "summary"]


class CategoryViewSet(SnippetViewSet):
    model = Category
    icon = "tag"
    menu_label = "دسته‌بندی محصولات"
    list_display = ["name", "name_en", "sort_order"]


class DirectoryGroup(SnippetViewSetGroup):
    items = (MemberViewSet, ProductViewSet, CategoryViewSet, RegionViewSet)
    menu_icon = "group"
    menu_label = "اعضا و فروشگاه"
    menu_name = "directory"
    menu_order = 150


register_snippet(DirectoryGroup)
