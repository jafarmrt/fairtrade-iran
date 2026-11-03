"""
Jalali dates wherever Django or Wagtail shows a date in Persian.

Django only knows the Gregorian calendar, so on Persian pages the Wagtail
admin showed dates like «۳ نوامبر ۲۰۲۶» (page history, listings, "locked
at", workflow timelines, date columns of our own snippet listings). This
module wraps django.utils.formats.date_format so that, when the active
language is Persian and the format asked for is one of the locale's
display formats (DATE_FORMAT, DATETIME_FORMAT, SHORT_DATE_FORMAT, …),
the date comes out in the Jalali calendar: «۱۲ آبان ۱۴۰۵، ساعت ۱۹:۵۵».

Explicit formats such as "c", "Y-m-d" or "Y-m-d H:i" are left alone,
so machine-readable values (datetime attributes, exports, inputs) and
English pages do not change. Installed by CoreConfig.ready().
"""

import datetime

from django.utils import formats
from django.utils.translation import get_language

from .jalali import MONTHS_FA, gregorian_to_jalali, to_persian_digits

DISPLAY_FORMATS = (
    "DATE_FORMAT", "DATETIME_FORMAT", "SHORT_DATE_FORMAT", "SHORT_DATETIME_FORMAT",
    "MONTH_DAY_FORMAT", "YEAR_MONTH_FORMAT",
)

_original_date_format = formats.date_format


def _persian_active():
    return (get_language() or "").split("-")[0] == "fa"


def _which_display_format(format_name, use_l10n):
    """The display format's name if `format_name` is (or resolves to) one, else None."""
    name = format_name or "DATE_FORMAT"
    if name in DISPLAY_FORMATS:
        return name
    # Wagtail's {% human_readable_date %} passes the resolved string, e.g. "j F Y، ساعت G:i".
    for candidate in DISPLAY_FORMATS:
        if formats.get_format(candidate, use_l10n=use_l10n) == name:
            return candidate
    return None


def jalali_text(value, kind="DATE_FORMAT"):
    """A date or datetime as Persian Jalali text in the style of the given display format."""
    y, m, d = gregorian_to_jalali(value.year, value.month, value.day)
    has_time = isinstance(value, datetime.datetime)
    time = f"{value.hour}:{value.minute:02d}" if has_time else ""
    if kind == "SHORT_DATE_FORMAT":
        text = f"{y}/{m:02d}/{d:02d}"
    elif kind == "SHORT_DATETIME_FORMAT":
        text = f"{y}/{m:02d}/{d:02d}" + (f"، {time}" if has_time else "")
    elif kind == "MONTH_DAY_FORMAT":
        text = f"{d} {MONTHS_FA[m - 1]}"
    elif kind == "YEAR_MONTH_FORMAT":
        text = f"{MONTHS_FA[m - 1]} {y}"
    elif kind == "DATETIME_FORMAT":
        text = f"{d} {MONTHS_FA[m - 1]} {y}" + (f"، ساعت {time}" if has_time else "")
    else:
        text = f"{d} {MONTHS_FA[m - 1]} {y}"
    return to_persian_digits(text)


def date_format(value, format=None, use_l10n=None):
    if use_l10n is not False and _persian_active() and isinstance(value, datetime.date):
        kind = _which_display_format(format, use_l10n)
        if kind:
            try:
                return jalali_text(value, kind)
            except (ValueError, IndexError, OverflowError):
                pass  # a date the converter cannot handle: show it the usual way
    return _original_date_format(value, format, use_l10n)


def install():
    """
    Replace django.utils.formats.date_format (used by localize() and the |date filter),
    and the copies that modules imported earlier hold (e.g. Wagtail's form submissions
    listing and active filters do `from django.utils.formats import date_format`).
    """
    import sys

    for module in list(sys.modules.values()):
        if getattr(module, "date_format", None) is _original_date_format:
            module.date_format = date_format
