"""A printable invoice (فاکتور فروش) for one order, shown to the buyer, the producer and staff."""

from django.template.response import TemplateResponse
from django.utils import translation

from core.models import SiteSettings

from .models import Seller


def render_invoice(request, order, back_url=""):
    purchase = order.purchase
    lang = translation.get_language() or "fa"
    return TemplateResponse(request, "shop/invoice.html", {
        "order": order,
        "purchase": purchase,
        "items": order.items.all(),
        "seller": Seller.for_member(order.member),
        "site": SiteSettings.load(request_or_site=request),
        "back_url": back_url,
        "LANG": lang[:2],
        "IS_EN": lang.startswith("en"),
        "DIR": "ltr" if lang.startswith("en") else "rtl",
    })
