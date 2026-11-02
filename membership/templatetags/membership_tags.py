from django import template

from core.models import is_english

from ..jalali import format_jalali, persian_digits

register = template.Library()


@register.filter
def jdate(value, style="long"):
    """A date in the reader's calendar: Jalali with Persian digits in Persian, Gregorian in English."""
    if not value:
        return ""
    if is_english():
        from ..jalali import as_date

        return as_date(value).strftime("%d %B %Y")
    return format_jalali(value, long=(style != "short"))


@register.filter
def jdate_fa(value, style="long"):
    """Always Jalali (used in the admin, which is in Persian)."""
    return format_jalali(value, long=(style != "short")) if value else ""


@register.filter
def fa_digits(value):
    if value in (None, ""):
        return ""
    return str(value) if is_english() else persian_digits(value)
