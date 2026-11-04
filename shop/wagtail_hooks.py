from wagtail.admin.viewsets.base import ViewSetGroup
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from core.admin_columns import MoneyColumn
from payments.wagtail_hooks import PaymentViewSet
from products.wagtail_hooks import CategoryViewSet, ProductViewSet
from wholesale.wagtail_hooks import inquiry_viewset

from .admin_views import OrdersViewSet
from .models import Seller


class SellerViewSet(SnippetViewSet):
    model = Seller
    icon = "group"
    menu_label = "فروشندگان"
    list_display = ["member", "mode", "commission_percent", MoneyColumn("shipping_fee", label="هزینه ارسال"), "updated_at"]
    list_filter = ["mode"]
    search_fields = ["member__name"]


class ShopGroup(ViewSetGroup):
    """
    «فروشگاه» in the admin menu: orders first (the daily work), then the catalogue,
    then the producers' payment settings and the payment log. Each person sees only
    the items their group has permission for.
    """

    menu_label = "فروشگاه"
    menu_name = "shop"  # the order of the main menu is set in core/wagtail_hooks.py
    menu_icon = "tag"
    items = (OrdersViewSet, inquiry_viewset, ProductViewSet, CategoryViewSet, SellerViewSet, PaymentViewSet)


register_snippet(ShopGroup)

# Orders waiting for staff are counted on the dashboard in «کارهای منتظر شما»
# (core.admin_views.pending_for).
