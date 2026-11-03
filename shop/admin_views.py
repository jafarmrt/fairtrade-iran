"""
Admin: «سفارش‌های فروشگاه». All orders with filters for what needs action,
one page per order with its history and the staff actions (confirm a receipt,
cancel, record settlement with the producer), and private receipt download.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from wagtail.admin.menu import MenuItem
from wagtail.admin.viewsets.base import ViewSet

from payments.models import Payment

from . import services
from .models import Order, Seller
from .panel_views import receipt_response


def can_manage(user):
    return user.is_active and (user.is_superuser or user.has_perm("shop.manage_orders"))


def require(request):
    if not can_manage(request.user):
        raise PermissionDenied


S = Order.Status
SETTLE_Q = Q(status__in=(S.PAID, S.SHIPPED, S.COMPLETED), settled_at__isnull=True) & (
    Q(payment_mode=Seller.Mode.HOUSE) | Q(commission__gt=0))
FILTERS = [
    ("todo", "رسید پرداخت به خانه در انتظار بررسی", Q(status=S.PAYMENT_REVIEW, payment_mode=Seller.Mode.HOUSE)),
    ("open", "در انتظار پرداخت", Q(status__in=Order.OPEN)),
    ("ship", "پرداخت‌شده، منتظر ارسال", Q(status=S.PAID)),
    ("settle", "تسویه‌نشده با تولیدکننده", SETTLE_Q),
    ("done", "ارسال‌شده و تحویل‌شده", Q(status__in=(S.SHIPPED, S.COMPLETED))),
    ("cancelled", "لغوشده", Q(status=S.CANCELLED)),
    ("all", "همه سفارش‌ها", Q()),
]


def index(request):
    require(request)
    show = request.GET.get("show", "all")
    q = request.GET.get("q", "").strip()
    condition = dict((k, c) for k, _, c in FILTERS).get(show, Q())
    qs = Order.objects.filter(condition).select_related("purchase", "member").order_by("-created_at")
    if q:
        qs = qs.filter(Q(purchase__code__icontains=q) | Q(purchase__buyer_name__icontains=q)
                       | Q(purchase__phone__icontains=q) | Q(member__name__icontains=q))
    counts = {k: Order.objects.filter(c).count() for k, _, c in FILTERS if k in ("todo", "ship", "settle")}
    totals = Order.objects.filter(status__in=(S.PAID, S.SHIPPED, S.COMPLETED)).aggregate(
        sales=Sum("total"), commission=Sum("commission"))
    return TemplateResponse(request, "shop/admin/index.html", {
        "page_title": "سفارش‌های فروشگاه",
        "header_icon": "pick",
        "orders": qs[:500],
        "show": show,
        "q": q,
        "filters": [(k, label) for k, label, _ in FILTERS],
        "counts": counts,
        "totals": totals,
    })


def detail(request, pk):
    require(request)
    order = get_object_or_404(Order.objects.select_related("purchase", "member"), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        message = request.POST.get("message", "")
        user = request.user
        try:
            if action == "confirm":
                services.confirm_payment(order, user, message=message)
            elif action == "reject":
                services.reject_payment(order, user, message)
            elif action == "ship":
                services.ship(order, user, request.POST.get("tracking_code", ""), message, by=services.STAFF)
            elif action == "complete":
                services.complete(order, user, by=services.STAFF)
            elif action == "cancel":
                services.cancel(order, user, message)
            elif action == "settle":
                services.settle(order, user, request.POST.get("reference", ""))
            elif action == "note":
                note = request.POST.get("staff_note", "")
                Order.objects.filter(pk=order.pk).update(staff_note=note)
            else:
                raise services.OrderError("اقدام ناشناخته.")
        except services.OrderError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, "ثبت شد.")
            return redirect("shop_orders:detail", pk=order.pk)
    purchase = order.purchase
    return TemplateResponse(request, "shop/admin/detail.html", {
        "page_title": f"سفارش {order.code}",
        "header_icon": "pick",
        "order": order,
        "purchase": purchase,
        "siblings": purchase.orders.exclude(pk=order.pk).select_related("member"),
        "events": order.events.select_related("user"),
        "payments": Payment.for_object(purchase),
        "seller": Seller.for_member(order.member),
    })


def receipt(request, pk):
    require(request)
    return receipt_response(get_object_or_404(Order, pk=pk))


class OrdersMenuItem(MenuItem):
    def is_shown(self, request):
        return can_manage(request.user)


class OrdersViewSet(ViewSet):
    name = "shop_orders"
    icon = "pick"
    menu_label = "سفارش‌های فروشگاه"
    menu_order = 105

    def get_urlpatterns(self):
        return [
            path("", index, name="index"),
            path("<int:pk>/", detail, name="detail"),
            path("<int:pk>/receipt/", receipt, name="receipt"),
        ]

    @property
    def menu_url(self):
        return reverse(self.get_url_name("index"))

    @property
    def menu_item_class(self):
        return OrdersMenuItem
