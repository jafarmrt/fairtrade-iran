from django.template.loader import render_to_string
from wagtail import hooks
from wagtail.admin.ui.components import Component
from wagtail.admin.viewsets.base import ViewSetGroup
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from payments.wagtail_hooks import PaymentViewSet
from products.wagtail_hooks import CategoryViewSet, ProductViewSet
from wholesale.wagtail_hooks import inquiry_viewset

from .admin_views import FILTERS, OrdersViewSet, can_manage
from .models import Order, Seller


class SellerViewSet(SnippetViewSet):
    model = Seller
    icon = "group"
    menu_label = "فروشندگان"
    list_display = ["member", "mode", "commission_percent", "shipping_fee", "updated_at"]
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


class OrdersPanel(Component):
    name = "shop_orders"
    order = 65

    def __init__(self, request):
        self.request = request

    def render_html(self, parent_context=None):
        if not can_manage(self.request.user):
            return ""
        labels = {"todo": "رسید پرداخت به خانه در انتظار بررسی", "ship": "سفارش پرداخت‌شده منتظر ارسال",
                  "settle": "سفارش تسویه‌نشده با تولیدکننده"}
        items = []
        for key, _, condition in FILTERS:
            if key in labels:
                count = Order.objects.filter(condition).count()
                if count:
                    items.append((count, labels[key], key))
        if not items:
            return ""
        return render_to_string("shop/admin/dashboard_panel.html", {"items": items}, request=self.request)


@hooks.register("construct_homepage_panels")
def add_orders_panel(request, panels):
    panels.append(OrdersPanel(request))
