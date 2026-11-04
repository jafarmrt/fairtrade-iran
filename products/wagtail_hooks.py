"""
Admin listings for products and their categories. They appear in the admin menu
in the «فروشگاه» group, registered by shop/wagtail_hooks.py.
"""

from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.ui.tables import BooleanColumn
from wagtail.snippets.views.snippets import SnippetViewSet

from core.admin_columns import EnglishColumn, MoneyColumn, english_filter

from .models import Category, Product


class ProductFilterSet(WagtailFilterSet):
    english = english_filter()

    class Meta:
        model = Product
        fields = ["member", "category", "in_stock", "is_published", "needs_review", "is_featured"]


class ProductViewSet(SnippetViewSet):
    model = Product
    icon = "tag"
    menu_label = "محصولات"
    list_display = [
        "name", "member", "category", MoneyColumn("price", label="قیمت"),
        BooleanColumn("in_stock", label="موجود است"),
        BooleanColumn("is_published", label="نمایش در سایت"),
        BooleanColumn("needs_review", label="در انتظار بررسی"),
        EnglishColumn(),
    ]
    filterset_class = ProductFilterSet
    search_fields = ["name", "name_en", "summary"]


class CategoryViewSet(SnippetViewSet):
    model = Category
    icon = "folder-inverse"
    menu_label = "دسته‌بندی محصولات"
    list_display = ["name", EnglishColumn(), "sort_order"]
