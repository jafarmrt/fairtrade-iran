"""
Money display. Amounts are always stored and sent to payment gateways in
rials; "تنظیمات سایت > نمایش مبلغ" chooses whether visitors see rials,
tomans (rial ÷ 10) or both. The choice is read once per request by
PriceDisplayMiddleware; e-mails and jobs outside a request read it directly.
"""

import contextvars
from decimal import Decimal

from django.utils.translation import get_language

RIAL, TOMAN, BOTH = "rial", "toman", "both"
UNITS = {RIAL: ("ریال", "rials"), TOMAN: ("تومان", "tomans")}

_mode = contextvars.ContextVar("price_display", default=None)


def display_mode():
    mode = _mode.get()
    if mode is None:
        from core.models import SiteSettings

        mode = SiteSettings.load().price_display
    return mode


def _english(lang=None):
    return (lang or get_language() or "fa")[:2] == "en"


def number(value, unit=RIAL, lang=None):
    """'۱۲٬۴۵۰٬۰۰۰' (or '12,450,000' in English) for a rial amount, in the given unit."""
    if value in (None, ""):
        return ""
    amount = Decimal(int(value))
    if unit == TOMAN:
        amount = amount / 10
    text = f"{amount:,.1f}".rstrip("0").rstrip(".") if amount % 1 else f"{int(amount):,}"
    if _english(lang):
        return text
    from core.iran import persian_digits

    return persian_digits(text).replace(",", "٬").replace(".", "٫")


def parse_amount(value, mode=None):
    """An amount typed in the display unit ('۲۰۰٬۰۰۰' tomans) as rials, or None when nothing usable was typed."""
    from core.iran import only_digits

    digits = only_digits(value)
    if not digits:
        return None
    amount = int(digits)
    return amount * 10 if primary_unit(mode) == TOMAN else amount


def primary_unit(mode=None):
    return RIAL if (mode or display_mode()) == RIAL else TOMAN


def unit_label(lang=None, mode=None):
    fa, en = UNITS[primary_unit(mode)]
    return en if _english(lang) else fa


def amount(value, lang=None, mode=None):
    """A rial amount with its unit: '۱٬۲۴۵٬۰۰۰ تومان', '12,450,000 rials', or toman with rials in brackets."""
    if value in (None, ""):
        return ""
    mode = mode or display_mode()
    en = _english(lang)
    unit = primary_unit(mode)
    text = f"{number(value, unit, lang)} {UNITS[unit][1 if en else 0]}"
    if mode == BOTH:
        text += f" ({number(value, RIAL, lang)} {UNITS[RIAL][1 if en else 0]})"
    return text


class PriceDisplayMiddleware:
    """Read the display setting once per request (Wagtail caches the settings on the request)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from core.models import SiteSettings

        try:
            mode = SiteSettings.load(request_or_site=request).price_display
        except Exception:  # no site yet (fresh install) or database not ready
            mode = None
        token = _mode.set(mode)
        try:
            return self.get_response(request)
        finally:
            _mode.reset(token)
