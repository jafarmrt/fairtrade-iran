"""E-mails and SMS about wholesale enquiries. None of these ever raise."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.mail import EmailMessage
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone, translation

from core.models import SiteSettings
from sms import notify as sms_notify
from sms import notify_role as sms_notify_role

from .models import WholesaleSettings

logger = logging.getLogger(__name__)


class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def base_url():
    return getattr(settings, "WAGTAILADMIN_BASE_URL", "").rstrip("/")


def _send(subject, body, to, reply_to=None):
    to = [a for a in to if a]
    if not to:
        return False
    try:
        EmailMessage(subject=subject.replace("\n", " "), body=body, from_email=settings.DEFAULT_FROM_EMAIL,
                     to=to, reply_to=reply_to or None).send()
    except Exception:  # an e-mail problem must never lose an enquiry
        logger.exception("Could not send wholesale e-mail")
        return False
    return True


def house_recipients():
    """Users allowed to handle enquiries (secretariat, market development), extra addresses, the house's address."""
    emails = set()
    perm = Permission.objects.filter(content_type__app_label="wholesale", codename="change_wholesaleinquiry").first()
    if perm is not None:
        users = get_user_model().objects.filter(is_active=True).filter(
            Q(groups__permissions=perm) | Q(user_permissions=perm)
        ).exclude(email="").distinct()
        emails.update(u.email for u in users)
    emails.update(a.strip() for a in WholesaleSettings.load().extra_recipients.split(",") if a.strip())
    house = SiteSettings.load().notification_email
    if house:
        emails.add(house)
    return sorted(emails)


def producer_emails(member):
    emails = {u.email for u in member.managers.filter(is_active=True).exclude(email="")}
    if member.public_email:
        emails.add(member.public_email)
    return sorted(emails)


def items_text(lines, en):
    s = WholesaleSettings.load()
    rows = []
    for line in lines:
        name = line.product_name
        if en and line.product_id and line.product.name_en:
            name = line.product.name_en
        rows.append(f"- {name}: {line.quantity} {s.unit_label(line.unit, en=en)}")
    return "\n".join(rows)


def site_name(lang):
    s = SiteSettings.load()
    return s.site_name_en if lang == "en" and s.site_name_en else s.site_name


def admin_link(inquiry):
    with translation.override("fa"):
        return base_url() + reverse("wholesale_inquiries:edit", args=[inquiry.pk])


def panel_link(share, lang="fa"):
    with translation.override(lang):
        return base_url() + reverse("panel:wholesale_detail", args=[share.member_id, share.pk])


# ---- when an enquiry arrives ----

def to_buyer(inquiry):
    s = WholesaleSettings.load()
    lang = "fa" if inquiry.language == "fa" else "en"
    subject, body = (s.buyer_subject, s.buyer_body) if lang == "fa" else (s.buyer_subject_en, s.buyer_body_en)
    lines = list(inquiry.lines.select_related("product"))
    items = items_text(lines, lang == "en")
    if inquiry.other_products:
        items = (items + "\n" if items else "") + inquiry.other_products
    values = SafeDict(name=inquiry.contact_name, company=inquiry.company, code=inquiry.tracking_code,
                      country=inquiry.country, items=items, site_name=site_name(lang))
    house = SiteSettings.load().notification_email
    return _send(subject.format_map(values), body.format_map(values), [inquiry.email],
                 reply_to=[house] if house else None)


def to_house(inquiry):
    lines = list(inquiry.lines.select_related("product", "member"))
    items = "\n".join(
        f"- {line.product_name} ({line.member.name if line.member else '—'}): "
        f"{line.quantity} {WholesaleSettings.load().unit_label(line.unit)}" for line in lines
    ) or "—"
    body = (
        f"درخواست سفارش عمده تازه در سایت ثبت شد.\n"
        f"کد پیگیری: {inquiry.tracking_code}\n\n"
        f"شرکت: {inquiry.company} ({inquiry.get_buyer_type_display()})\n"
        f"نام: {inquiry.contact_name}\n"
        f"ایمیل: {inquiry.email}\n"
        f"تلفن: {inquiry.phone or '—'}\n"
        f"کشور و شهر: {inquiry.country} {inquiry.city}\n"
        f"شرایط تحویل: {inquiry.incoterm or '—'} · مقصد: {inquiry.destination or '—'}\n"
        f"زمان مورد نیاز: {inquiry.needed_by or '—'}\n\n"
        f"محصولات:\n{items}\n\n"
    )
    if inquiry.other_products:
        body += f"محصولات دیگر یا سفارش سفارشی:\n{inquiry.other_products}\n\n"
    if inquiry.message:
        body += f"توضیحات خریدار:\n{inquiry.message}\n\n"
    body += f"برای رسیدگی و دیدن پاسخ تولیدکنندگان:\n{admin_link(inquiry)}\n"
    sent = _send(f"سفارش عمده تازه: {inquiry.tracking_code} – {inquiry.company} ({inquiry.country})",
                 body, house_recipients(), reply_to=[inquiry.email])
    sms_notify_role("wholesale_new", "secretariat", {
        "code": inquiry.tracking_code, "company": inquiry.company, "country": inquiry.country,
        "admin_url": admin_link(inquiry), "site_name": site_name("fa"),
    })
    return sent


def to_producer(share):
    """Tell one producer about an enquiry for their products, once."""
    s = WholesaleSettings.load()
    member, inquiry = share.member, share.inquiry
    lines = list(share.lines().select_related("product"))
    url = panel_link(share)
    context = SafeDict(
        name=member.name, code=inquiry.tracking_code, country=inquiry.country,
        buyer_type=inquiry.get_buyer_type_display(), incoterm=inquiry.incoterm or "—",
        destination=inquiry.destination or "—", needed_by=inquiry.needed_by or "—",
        items=items_text(lines, False) or inquiry.other_products, panel_url=url, site_name=site_name("fa"),
    )
    _send(s.producer_subject.format_map(context), s.producer_body.format_map(context), producer_emails(member))
    if member.public_phone:
        sms_notify("wholesale_producer", member.public_phone, dict(context), lang="fa")
    share.notified_at = timezone.now()
    share.save(update_fields=["notified_at"])


def notify_new_shares(inquiry):
    for share in inquiry.producers.filter(notified_at__isnull=True).select_related("member"):
        if share.member.is_inactive:
            continue
        try:
            to_producer(share)
        except Exception:
            logger.exception("Could not notify producer about wholesale enquiry %s", inquiry.pk)


def submitted(inquiry):
    to_buyer(inquiry)
    to_house(inquiry)
    if WholesaleSettings.load().notify_producers:
        notify_new_shares(inquiry)


# ---- when a producer answers ----

def producer_replied(share):
    inquiry = share.inquiry
    with translation.override("fa"):
        status = share.get_status_display()
    body = (
        f"«{share.member.name}» به درخواست سفارش عمده {inquiry.tracking_code} ({inquiry.company}، "
        f"{inquiry.country}) پاسخ داد.\n\n"
        f"پاسخ: {status}\n"
        f"قیمت پیشنهادی: {share.price_quote or '—'}\n"
        f"زمان آماده‌سازی: {share.lead_time or '—'}\n"
        f"توضیح: {share.reply or '—'}\n\n"
        f"{admin_link(inquiry)}\n"
    )
    _send(f"پاسخ تولیدکننده به سفارش عمده {inquiry.tracking_code}", body, house_recipients())
    sms_notify_role("wholesale_reply", "secretariat", {
        "name": share.member.name, "code": inquiry.tracking_code, "status": status,
        "admin_url": admin_link(inquiry),
    })
