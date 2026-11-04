import datetime

from django import template
from django.utils import timezone
from django.utils.dateformat import format as django_format

from core.jalali import format_jalali, to_persian_digits
from core.models import is_english

register = template.Library()


def _local(value):
    if isinstance(value, datetime.datetime) and timezone.is_aware(value):
        return timezone.localtime(value)
    return value


@register.filter
def jdate(value):
    """Jalali date on Persian pages, '2 November 2026' on English pages."""
    if not value:
        return ""
    if is_english():
        return django_format(_local(value), "j F Y")
    return format_jalali(value)


@register.filter
def jdatetime(value):
    """Like jdate, with the time for datetimes."""
    if not value:
        return ""
    if is_english():
        fmt = "j F Y, H:i" if isinstance(value, datetime.datetime) else "j F Y"
        return django_format(_local(value), fmt)
    return format_jalali(value, with_time=True)


@register.filter
def jtime(value):
    """'18:30', in Persian digits on Persian pages."""
    if not value:
        return ""
    text = f"{_local(value):%H:%M}"
    return text if is_english() else to_persian_digits(text)


@register.filter
def jinput(value):
    """1405/08/12 (Latin digits) for the value of a Jalali date input."""
    if not value:
        return ""
    from core.widgets import jalali_text

    return jalali_text(_local(value).date() if isinstance(value, datetime.datetime) else value)


@register.simple_tag
def this_year():
    """This year for a footer: '۱۴۰۵' on Persian pages, '2026' on English pages."""
    today = timezone.localdate()
    if is_english():
        return str(today.year)
    from core.jalali import gregorian_to_jalali

    return to_persian_digits(gregorian_to_jalali(today.year, today.month, today.day)[0])
