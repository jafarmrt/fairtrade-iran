"""The public wholesale page (catalogue + enquiry form) and the producers' pages in the member panel."""

import datetime
from itertools import groupby

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone

from core.models import is_english
from core.throttle import client_ip
from memberpanel.views import member_view, render, t
from products.models import Product
from sms.phone import DIGITS

from . import notifications
from .forms import InquiryForm, ReplyForm, seconds_since, started_token
from .models import ProducerShare, WholesaleInquiry, WholesaleInquiryLine, WholesaleSettings, hash_ip

CLOSED_STATUSES = ("ordered", "closed", "spam")
HONEYPOT_FIELD = "fax_number"  # hidden from people; "website" is a real field here


def catalogue_products():
    return Product.visible().order_by("member__sort_order", "member__name", "sort_order", "-created_at")


def catalogue_groups(products):
    """Products grouped by producer, in the producers' display order."""
    return [{"member": member, "products": list(items)} for member, items in groupby(products, key=lambda p: p.member)]


def parse_quantity(raw):
    raw = (raw or "").strip().translate(DIGITS).replace(",", "").replace("٬", "")
    if not raw:
        return None, False
    if not raw.isdigit() or int(raw) <= 0 or int(raw) > 10_000_000:
        return None, True
    return int(raw), False


def read_lines(post, products, settings):
    """Quantities typed next to the products. Sets wh_qty / wh_unit / wh_error on each product for re-display."""
    units = [value for value, _ in settings.unit_choices()]
    lines, bad = [], []
    for product in products:
        raw = post.get(f"qty_{product.pk}", "")
        quantity, invalid = parse_quantity(raw)
        unit = post.get(f"unit_{product.pk}", "")
        product.wh_qty = raw.strip()[:12]
        product.wh_unit = unit if unit in units else (units[0] if units else "")
        product.wh_error = invalid
        if invalid:
            bad.append(product)
        elif quantity:
            lines.append((product, quantity, product.wh_unit))
    return lines, bad


def too_many_recent(ip_hash, settings):
    if not ip_hash or not settings.max_per_hour:
        return False
    since = timezone.now() - datetime.timedelta(hours=1)
    return WholesaleInquiry.objects.filter(ip_hash=ip_hash, created_at__gte=since).count() >= settings.max_per_hour


@transaction.atomic
def save_inquiry(form, lines, request, settings):
    inquiry = form.save(commit=False)
    inquiry.language = "en" if is_english() else "fa"
    inquiry.ip_hash = hash_ip(client_ip(request))
    inquiry.save()
    members = []
    for product, quantity, unit in lines:
        WholesaleInquiryLine.objects.create(
            inquiry=inquiry, product=product, member=product.member, product_name=product.name,
            quantity=quantity, unit=unit,
        )
        if product.member not in members:
            members.append(product.member)
    if settings.notify_producers:
        for member in members:
            ProducerShare.objects.create(inquiry=inquiry, member=member)
    transaction.on_commit(lambda: notifications.submitted(inquiry))
    return inquiry


def _response(request, template, context):
    response = TemplateResponse(request, template, context)
    response["Cache-Control"] = "no-store"
    return response


def serve_wholesale_page(page, request):
    settings = WholesaleSettings.load(request_or_site=request)
    products = list(catalogue_products())
    selected = request.GET.get("product", "")
    for product in products:
        product.wh_qty, product.wh_unit, product.wh_error = "", "", False
        product.wh_selected = product.slug == selected
    errors = []
    form = None

    if request.method == "POST" and settings.enabled:
        if request.POST.get(HONEYPOT_FIELD):  # bots fill every field; pretend all went well
            return _response(request, "wholesale/wholesale_page_landing.html",
                             dict(page.get_context(request), inquiry=None))
        form = InquiryForm(request.POST, settings=settings)
        lines, bad = read_lines(request.POST, products, settings)
        valid = form.is_valid()
        if bad:
            errors.append(t("مقدار برخی محصولات درست نیست؛ فقط عدد صحیح بنویسید.",
                            "Some quantities are not valid. Please use whole numbers."))
        if valid and not lines and not form.cleaned_data.get("other_products", "").strip():
            errors.append(t("دست‌کم برای یک محصول مقدار بنویسید، یا در «محصولات دیگر» بگویید چه می‌خواهید.",
                            "Please enter a quantity for at least one product, or describe what you need under “Other products”."))
        if settings.max_lines and len(lines) > settings.max_lines:
            errors.append(t(f"در هر درخواست حداکثر {settings.max_lines} محصول می‌توانید بفرستید.",
                            f"You can include up to {settings.max_lines} products in one enquiry."))
        elapsed = seconds_since(request.POST.get("started"))
        if elapsed is None or elapsed < settings.min_seconds:
            errors.append(t("لطفاً فرم را بازبینی کنید و دوباره بفرستید.", "Please check the form and send it again."))
        elif too_many_recent(hash_ip(client_ip(request)), settings):
            errors.append(t("از این نشانی درخواست‌های زیادی رسیده است. لطفاً کمی بعد دوباره بفرستید یا با ما تماس بگیرید.",
                            "We have received many enquiries from your connection. Please try again later or contact us."))
        if valid and not errors:
            inquiry = save_inquiry(form, lines, request, settings)
            return _response(request, "wholesale/wholesale_page_landing.html",
                             dict(page.get_context(request), inquiry=inquiry))
    elif settings.enabled:
        form = InquiryForm(settings=settings)

    unit_choices = settings.unit_choices()
    for product in products:
        if not product.wh_unit and unit_choices:
            product.wh_unit = unit_choices[0][0]
    context = page.get_context(request)
    context.update({
        "form": form,
        "errors": errors,
        "groups": catalogue_groups(products),
        "product_count": len(products),
        "unit_choices": unit_choices,
        "wholesale_settings": settings,
        "started_token": started_token(),
        "selected": selected,
        "honeypot": HONEYPOT_FIELD,
    })
    return _response(request, page.get_template(request), context)


# ---- member panel ----

def _shares(member):
    return (member.wholesale_shares.exclude(inquiry__status="spam")
            .select_related("inquiry").order_by("-inquiry__created_at"))


@member_view(editing=False)
def inquiry_list(request, member):
    shares = list(_shares(member))
    for share in shares:
        share.own_lines = list(share.lines())
    return render(request, "wholesale/panel/inquiry_list.html",
                  {"member": member, "shares": shares, "current": "wholesale"})


@member_view(editing=False)
def inquiry_detail(request, member, share_id):
    share = get_object_or_404(_shares(member), pk=share_id)
    settings = WholesaleSettings.load(request_or_site=request)
    if share.status == ProducerShare.Status.NEW:
        share.status = ProducerShare.Status.SEEN
        share.save(update_fields=["status"])
    can_reply = not member.is_inactive and share.inquiry.status not in CLOSED_STATUSES
    form = ReplyForm(request.POST or None, instance=share) if can_reply else None
    if request.method == "POST" and form is not None and form.is_valid():
        with transaction.atomic():
            share = form.save(commit=False)
            share.replied_at = timezone.now()
            share.replied_by = request.user
            share.save()
            transaction.on_commit(lambda: notifications.producer_replied(share))
        messages.success(request, t("پاسخ شما به دبیرخانه خانه رسید. سپاس!",
                                    "Thank you, your answer has reached the House's secretariat."))
        return redirect("panel:wholesale", member_id=member.pk)
    return render(request, "wholesale/panel/inquiry_detail.html", {
        "member": member, "share": share, "inquiry": share.inquiry, "lines": share.lines().select_related("product"),
        "form": form, "show_contact": settings.share_buyer_contact, "current": "wholesale",
    })
