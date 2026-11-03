"""
E-mails and SMS about orders. Texts are EmailTemplate snippets (events order_*,
defaults in membership/email_defaults.py) and SMS templates (shop/sms_events.py).
"""

from django.urls import reverse
from django.utils import translation
from wagtail.models import Locale

from core import money
from core.models import SiteSettings
from membership.jalali import persian_digits
from membership.notifications import base_url, recipients_for, send
from products.models import ProductIndexPage, ShopSettings
from sms import notify as sms_notify
from sms import notify_role as sms_notify_role
from standing.notifications import member_phone, member_recipients


def amount_text(value, lang):
    return money.amount(value or 0, lang)


def shop_url(lang, suffix=""):
    try:
        locale = Locale.objects.get(language_code=lang)
    except Locale.DoesNotExist:
        return ""
    page = ProductIndexPage.objects.live().filter(locale=locale).first()
    if page is None:
        return ""
    url = page.get_url() or ""
    if url.startswith("/"):
        url = base_url() + url
    return url + suffix


def order_url(purchase, lang):
    return shop_url(lang, f"order/{purchase.code}/")


def panel_url(order):
    with translation.override("fa"):
        return base_url() + reverse("panel:order", kwargs={"member_id": order.member_id, "order_id": order.pk})


def admin_url(order=None):
    if order is None:
        return base_url() + reverse("shop_orders:index")
    return base_url() + reverse("shop_orders:detail", args=[order.pk])


def member_name(member, lang):
    return member.name_en if (lang == "en" and member.name_en) else member.name


def items_text(order, lang):
    lines = []
    for item in order.items.all():
        name = item.name_en if (lang == "en" and item.name_en) else item.name
        qty = item.quantity if lang == "en" else persian_digits(item.quantity)
        lines.append(f"- {name} × {qty}: {amount_text(item.line_total, lang)}")
    if order.shipping:
        lines.append(("Shipping" if lang == "en" else "هزینه ارسال") + f": {amount_text(order.shipping, lang)}")
    lines.append(("Total" if lang == "en" else "جمع") + f": {amount_text(order.total, lang)}")
    return "\n".join(lines)


def account_text(account, lang):
    rows = [("به نام", "Account holder", account.account_holder), ("بانک", "Bank", account.bank_name),
            ("شماره کارت", "Card number", account.card_number), ("شماره شبا", "IBAN (Sheba)", account.sheba)]
    return "\n".join(f"  {en if lang == 'en' else fa}: {v}" for fa, en, v in rows if v)


def payment_text(order, lang):
    """How the buyer pays this order."""
    from .models import Seller

    en = lang == "en"
    if order.is_house:
        account = ShopSettings.load().house_account()
        head = ("Pay to the Fair Trade House" if en else "پرداخت به حساب خانه تجارت عادلانه")
    else:
        account = Seller.for_member(order.member)
        head = ("Pay directly to the producer" if en else "پرداخت مستقیم به حساب تولیدکننده")
    text = account_text(account, lang)
    return f"{head}{':' if text else ''}\n{text}" if text else head


def purchase_details(purchase, lang):
    parts = []
    for order in purchase.orders.all():
        parts.append(f"{member_name(order.member, lang)} ({order.code}):\n{items_text(order, lang)}\n"
                     f"{payment_text(order, lang)}")
    return "\n\n".join(parts)


def context(purchase, lang, order=None, message=""):
    with translation.override(lang):
        ctx = {
            "name": purchase.buyer_name,
            "code": purchase.code,
            "order_url": order_url(purchase, lang),
            "total": amount_text(purchase.total, lang),
            "details": purchase_details(purchase, lang),
            "buyer": f"{purchase.buyer_name} - {purchase.phone}" + (f" - {purchase.email}" if purchase.email else ""),
            "address": purchase.full_address,
            "message": message,
            "site_name": SiteSettings.load().tr("site_name"),
            "admin_url": admin_url(order),
        }
        if order is not None:
            ctx.update({
                "code": order.code,
                "member": member_name(order.member, lang),
                "details": items_text(order, lang),
                "total": amount_text(order.total, lang),
                "payment": payment_text(order, lang),
                "payment_mode": order.get_payment_mode_display(),
                "tracking": order.tracking_code or "-",
                "panel_url": panel_url(order),
                "status": order.status_display,
            })
        return ctx


def buyer_lang(purchase):
    return purchase.language if purchase.language in ("fa", "en") else "fa"


def to_buyer(purchase, event, order=None, message=""):
    lang = buyer_lang(purchase)
    ctx = context(purchase, lang, order, message)
    sms_notify(event, purchase.phone, ctx, lang)
    return send(event, [purchase.email] if purchase.email else [], lang, ctx)


def seller_recipients(member):
    from .models import Seller

    emails = set(member_recipients(member))
    seller = Seller.for_member(member)
    if seller.order_email:
        emails.add(seller.order_email)
    return sorted(emails)


def to_seller(order, event, message=""):
    from .models import Seller

    ctx = context(order.purchase, "fa", order, message)
    mobile = Seller.for_member(order.member).order_mobile or member_phone(order.member)
    sms_notify(event, mobile, ctx, "fa")
    return send(event, seller_recipients(order.member), "fa", ctx)


def staff_recipients():
    email = ShopSettings.load().order_notification_email
    return [email] if email else recipients_for("secretariat")


def to_staff(event, purchase, order=None, message=""):
    ctx = context(purchase, "fa", order, message)
    sms_notify_role(event, "secretariat", ctx)
    return send(event, staff_recipients(), "fa", ctx)


# ---- hooks called by services ----


def placed(purchase):
    to_buyer(purchase, "order_placed")
    shop = ShopSettings.load()
    for order in purchase.orders.all():
        to_seller(order, "order_seller_new")
    if shop.notify_staff_all_orders or any(o.is_house for o in purchase.orders.all()):
        to_staff("order_staff_new", purchase)


def receipt(order):
    if order.is_house:
        to_staff("order_receipt", order.purchase, order, order.payer_note)
    else:
        to_seller(order, "order_seller_receipt", order.payer_note)


def paid(order):
    to_buyer(order.purchase, "order_paid", order)
    to_seller(order, "order_seller_paid")


def rejected(order, message):
    to_buyer(order.purchase, "order_rejected", order, message)


def shipped(order):
    to_buyer(order.purchase, "order_shipped", order, order.shipping_message)


def cancelled(order, was_paid, by):
    to_buyer(order.purchase, "order_cancelled", order, order.cancel_reason)
    if by != "seller":
        to_seller(order, "order_cancelled", order.cancel_reason)
    if was_paid and order.is_house:
        to_staff("order_cancelled", order.purchase, order, order.cancel_reason)
