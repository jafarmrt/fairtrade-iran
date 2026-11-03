"""Member panel: the orders a producer received through the site, and its selling settings."""

import mimetypes

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from core.models import is_english
from memberpanel.views import member_view, render, t

from products.models import ShopSettings

from . import services
from .forms import SellerForm, ShippingOptionFormSet
from .models import Order, Seller

FILTERS = [
    ("todo", ("نیاز به اقدام", "Needs action")),
    ("open", ("در انتظار پرداخت", "Awaiting payment")),
    ("done", ("ارسال‌شده و تحویل‌شده", "Shipped and delivered")),
    ("cancelled", ("لغوشده و مرجوعی", "Cancelled and returned")),
    ("all", ("همه", "All")),
]


def todo_q(member):
    """Orders the producer has to act on: paid ones to ship, and direct payments to confirm."""
    S = Order.Status
    qs = member.orders.all()
    return qs.filter(status=S.PAID) | qs.filter(status=S.PAYMENT_REVIEW, payment_mode=Seller.Mode.PRODUCER)


@member_view(editing=False)
def orders(request, member):
    show = request.GET.get("show", "todo")
    S = Order.Status
    qs = {
        "todo": todo_q(member),
        "open": member.orders.filter(status__in=Order.OPEN),
        "done": member.orders.filter(status__in=(S.SHIPPED, S.COMPLETED)),
        "cancelled": member.orders.filter(status__in=(S.CANCELLED, S.RETURNED)),
    }.get(show, member.orders.all())
    i = 1 if is_english() else 0
    return render(request, "shop/panel/orders.html", {
        "member": member,
        "orders": qs.select_related("purchase").prefetch_related("items").order_by("-created_at")[:200],
        "show": show,
        "filters": [(key, pair[i]) for key, pair in FILTERS],
        "seller": Seller.for_member(member),
        "current": "orders",
    })


@member_view(editing=False)
def order_detail(request, member, order_id):
    order = get_object_or_404(member.orders.select_related("purchase"), pk=order_id)
    if request.method == "POST":
        action = request.POST.get("action")
        message = request.POST.get("message", "")
        try:
            if action == "confirm" and not order.is_house:
                services.confirm_payment(order, request.user, by=services.SELLER, message=message)
            elif action == "reject" and not order.is_house:
                services.reject_payment(order, request.user, message, by=services.SELLER)
            elif action == "ship":
                services.ship(order, request.user, request.POST.get("tracking_code", ""), message)
            elif action == "complete":
                services.complete(order, request.user)
            elif action == "cancel":
                services.cancel(order, request.user, message, by=services.SELLER)
            elif action == "refund" and services.can_record_refund(order, services.SELLER):
                services.refund(order, request.user, refund_amount(request.POST.get("refund_amount"), order),
                                request.POST.get("refund_reference", ""), message,
                                restock=request.POST.get("restock") == "1", by=services.SELLER)
            else:
                raise services.OrderError(t("این اقدام برای این سفارش ممکن نیست.", "This action is not possible."))
        except services.OrderError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, t("ثبت شد و به خریدار خبر داده شد.", "Saved; the buyer has been notified."))
            return redirect("panel:order", member_id=member.pk, order_id=order.pk)
    return render(request, "shop/panel/order.html", {
        "member": member,
        "order": order,
        "purchase": order.purchase,
        "can_cancel": services.seller_can_cancel(order),
        "can_refund": order.status in Order.REFUNDABLE and services.can_record_refund(order, services.SELLER),
        "events": order.events.all(),
        "current": "orders",
    })


def refund_amount(value, order):
    """The refund amount typed in the page's unit (toman or rial), in rials; empty means the whole order."""
    from core import money
    from core.iran import only_digits

    digits = only_digits(value or "")
    if not digits:
        return order.total
    amount = int(digits)
    return amount * 10 if money.primary_unit() == money.TOMAN else amount


@member_view(editing=False)
def order_invoice(request, member, order_id):
    from .invoice import render_invoice

    order = get_object_or_404(member.orders.select_related("purchase"), pk=order_id)
    return render_invoice(request, order, back_url=reverse("panel:order", args=[member.pk, order.pk]))


@member_view(editing=False)
def order_receipt(request, member, order_id):
    """The receipt a buyer uploaded for a direct payment, for the producer to check."""
    order = get_object_or_404(member.orders.all(), pk=order_id, payment_mode=Seller.Mode.PRODUCER)
    return receipt_response(order)


def receipt_response(order):
    if not order.receipt:
        raise Http404
    try:
        handle = order.receipt.open("rb")
    except FileNotFoundError:
        raise Http404
    name = order.receipt_filename
    response = FileResponse(handle, as_attachment=True, filename=name,
                            content_type=mimetypes.guess_type(name)[0] or "application/octet-stream")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@member_view()
def selling(request, member):
    seller = Seller.for_member(member)
    form = SellerForm(request.POST or None, instance=seller)
    options = ShippingOptionFormSet(request.POST or None, instance=seller, prefix="ship")
    if request.method == "POST" and form.is_valid() and options.is_valid():
        seller = form.save()
        options.instance = seller
        options.save()
        messages.success(request, t("تنظیمات فروش ذخیره شد.", "Your selling settings were saved."))
        return redirect("panel:selling", member_id=member.pk)
    groups = [
        (t("حساب بانکی", "Bank account"), ["account_holder", "bank_name", "card_number", "sheba"]),
        (t("ارسال", "Shipping"), ["shipping_fee", "free_shipping_over", "prep_days", "shipping_note", "shipping_note_en"]),
        (t("خبر سفارش‌ها", "Order notifications"), ["order_mobile", "order_email"]),
    ]
    return render(request, "shop/panel/selling.html", {
        "member": member, "form": form, "seller": seller, "current": "selling", "options": options,
        "fieldsets": [(legend, [form[name] for name in names]) for legend, names in groups],
        "commission": seller.effective_commission(ShopSettings.load()),
    })
