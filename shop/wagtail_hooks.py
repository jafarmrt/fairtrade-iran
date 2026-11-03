from django.template.loader import render_to_string
from wagtail import hooks
from wagtail.admin.ui.components import Component
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from payments.wagtail_hooks import PaymentViewSet

from .admin_views import FILTERS, OrdersViewSet, can_manage
from .models import Order, Seller


@hooks.register("register_admin_viewset")
def register_orders_viewset():
    return OrdersViewSet()


class SellerViewSet(SnippetViewSet):
    model = Seller
    icon = "group"
    menu_label = "فروشندگان"
    list_display = ["member", "mode", "commission_percent", "shipping_fee", "updated_at"]
    list_filter = ["mode"]
    search_fields = ["member__name"]


class SalesGroup(SnippetViewSetGroup):
    menu_label = "فروش و پرداخت"
    menu_icon = "pick"
    menu_order = 106
    items = (SellerViewSet, PaymentViewSet)


register_snippet(SalesGroup)


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
