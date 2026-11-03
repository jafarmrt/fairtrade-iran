"""
Admin: «سفارش‌های فروشگاه». All orders with filters for what needs action,
one page per order with its history and the staff actions (confirm a receipt,
cancel, record settlement with the producer), and private receipt download.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from urllib.parse import urlencode

from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from wagtail.admin.menu import MenuItem
from wagtail.admin.viewsets.base import ViewSet

from payments.models import Payment

from . import services
from .models import Order, Seller
from .invoice import render_invoice
from .panel_views import receipt_response, refund_amount
from core.exports import add_months, csv_response, jalali_stamp, jalali_today, month_bounds, month_name, parse_month
from core.iran import persian_digits, text_search


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
    ("returns", "درخواست مرجوعی بررسی‌نشده", Q(return_requested_at__isnull=False) & ~Q(status=S.RETURNED)),
    ("cancelled", "لغوشده و مرجوعی", Q(status__in=(S.CANCELLED, S.RETURNED))),
    ("all", "همه سفارش‌ها", Q()),
]


def index(request):
    require(request)
    show = request.GET.get("show", "all")
    q = request.GET.get("q", "").strip()
    condition = dict((k, c) for k, _, c in FILTERS).get(show, Q())
    qs = Order.objects.filter(condition).select_related("purchase", "member").order_by("-created_at")
    if q:
        qs = qs.filter(text_search(q, "purchase__code", "purchase__buyer_name", "purchase__phone", "member__name"))
    if request.GET.get("export") == "csv":
        return export_orders(qs, "orders")
    counts = {k: Order.objects.filter(c).count() for k, _, c in FILTERS if k in ("todo", "ship", "settle", "returns")}
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
        "export_query": urlencode({"show": show, "q": q, "export": "csv"}),
    })


ORDER_HEADER = ["کد سفارش", "تاریخ ثبت", "خریدار", "تلفن", "ایمیل", "استان", "شهر", "نشانی", "کد پستی",
                "تولیدکننده", "پرداخت به", "پرداخت آنلاین", "شماره پیگیری پرداخت", "تاریخ پرداخت",
                "روش ارسال", "جمع کالاها (ریال)", "هزینه ارسال (ریال)", "مبلغ کل (ریال)", "درصد کارمزد",
                "کارمزد (ریال)", "سهم تولیدکننده (ریال)", "وضعیت", "تاریخ ارسال", "کد رهگیری", "تاریخ تحویل",
                "تاریخ تسویه", "شماره تسویه", "درخواست مرجوعی", "مبلغ بازپرداخت (ریال)", "تاریخ بازپرداخت", "اقلام"]


def order_row(o):
    p = o.purchase
    return [
        o.code, jalali_stamp(o.created_at), p.buyer_name, p.phone, p.email, p.province,
        p.city, p.address, p.postal_code, o.member.name,
        "خانه" if o.is_house else "تولیدکننده", "بله" if o.paid_online else "", o.payment_reference,
        jalali_stamp(o.paid_at), o.shipping_method, o.subtotal, o.shipping, o.total, o.commission_percent,
        o.commission, o.producer_share, o.get_status_display(), jalali_stamp(o.shipped_at), o.tracking_code,
        jalali_stamp(o.completed_at), jalali_stamp(o.settled_at), o.settlement_reference,
        jalali_stamp(o.return_requested_at), o.refund_amount or "", jalali_stamp(o.refunded_at),
        "؛ ".join(f"{i.name} × {i.quantity}" for i in o.items.all()),
    ]


def export_orders(qs, name):
    qs = qs.select_related("purchase", "member").prefetch_related("items")
    y, m, d = jalali_today()
    return csv_response(f"{name}-{y}{m:02d}{d:02d}.csv", ORDER_HEADER, (order_row(o) for o in qs.iterator(chunk_size=500)))


SOLD = (S.PAID, S.SHIPPED, S.COMPLETED, S.RETURNED)


def _summary(qs):
    return qs.aggregate(count=Count("pk"), sales=Sum("total"), subtotal=Sum("subtotal"), shipping=Sum("shipping"),
                        commission=Sum("commission"), refunds=Sum("refund_amount"))


def report(request):
    """Jalali monthly sales: the last twelve months, and one month by producer (with its CSV)."""
    require(request)
    jy, jm = parse_month(request.GET.get("month")) or jalali_today()[:2]
    start, end = month_bounds(jy, jm)
    # A sale counts in the month it was paid (online or confirmed receipt).
    month_qs = Order.objects.filter(status__in=SOLD, paid_at__gte=start, paid_at__lt=end)
    if request.GET.get("export") == "csv":
        return export_orders(month_qs.order_by("paid_at"), f"sales-{jy}-{jm:02d}")
    months = []
    for n in range(11, -1, -1):
        y, m = add_months(jy, jm, -n)
        s, e = month_bounds(y, m)
        row = _summary(Order.objects.filter(status__in=SOLD, paid_at__gte=s, paid_at__lt=e))
        months.append({"key": f"{y}-{m:02d}", "label": f"{month_name(m)} {y}", "current": (y, m) == (jy, jm), **row})
    producers = (month_qs.values("member__name").annotate(
        count=Count("pk"), sales=Sum("total"), commission=Sum("commission"), refunds=Sum("refund_amount"),
        house=Sum("total", filter=Q(payment_mode=Seller.Mode.HOUSE))).order_by("-sales"))
    prev, nxt = add_months(jy, jm, -1), add_months(jy, jm, 1)
    return TemplateResponse(request, "shop/admin/report.html", {
        "page_title": persian_digits(f"گزارش فروش {month_name(jm)} {jy}"),
        "header_icon": "pick",
        "month_label": f"{month_name(jm)} {jy}",
        "month_key": f"{jy}-{jm:02d}",
        "prev_key": f"{prev[0]}-{prev[1]:02d}",
        "next_key": f"{nxt[0]}-{nxt[1]:02d}",
        "summary": _summary(month_qs),
        "months": months,
        "producers": producers,
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
            elif action == "refund":
                services.refund(order, user, refund_amount(request.POST.get("refund_amount"), order),
                                request.POST.get("refund_reference", ""), message,
                                restock=request.POST.get("restock") == "1")
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


def invoice(request, pk):
    require(request)
    order = get_object_or_404(Order.objects.select_related("purchase", "member"), pk=pk)
    return render_invoice(request, order, back_url=reverse("shop_orders:detail", args=[order.pk]))


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
            path("<int:pk>/invoice/", invoice, name="invoice"),
            path("report/", report, name="report"),
        ]

    @property
    def menu_url(self):
        return reverse(self.get_url_name("index"))

    @property
    def menu_item_class(self):
        return OrdersMenuItem
