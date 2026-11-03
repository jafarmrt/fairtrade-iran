from django import template

from core.jalali import format_jalali

register = template.Library()


@register.filter
def jdatetime_fa(value):
    """Jalali date and time, always in Persian (the admin is in Persian)."""
    return format_jalali(value, with_time=True) if value else ""
