"""
Jalali (Solar Hijri) date inputs for the Wagtail admin and our own forms.
Staff type 1405/08/12 (Persian or Latin digits, / or -); a Gregorian date
such as 2026-11-03 is accepted too. The database keeps Gregorian dates.
"""

import datetime

from django import forms
from django.utils import timezone

from membership.jalali import format_jalali, parse_date, to_jalali

LATIN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def jalali_text(day):
    y, m, d = to_jalali(day.year, day.month, day.day)
    return f"{y}/{m:02d}/{d:02d}"


class JalaliDateInput(forms.TextInput):
    template_name = "core/widgets/jalali_date.html"
    example = "1405/08/12"

    def __init__(self, attrs=None):
        attrs = {"dir": "ltr", "inputmode": "numeric", "autocomplete": "off", "class": "jalali-date",
                 "size": 12, **(attrs or {})}
        super().__init__(attrs)

    def format_value(self, value):
        if isinstance(value, datetime.datetime):
            value = value.date()
        if isinstance(value, datetime.date):
            return jalali_text(value)
        return super().format_value(value)

    def value_from_datadict(self, data, files, name):
        raw = data.get(name)
        if not raw:
            return raw
        day = parse_date(raw)
        return day.isoformat() if day else raw  # an invalid value reaches the field and shows its error

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["attrs"].setdefault("placeholder", self.example)
        context["today"] = format_jalali(timezone.localdate())
        return context


class JalaliDateTimeInput(JalaliDateInput):
    """1405/08/12 18:30 (the time is optional and means 00:00 when left out)."""

    example = "1405/08/12 18:30"

    def __init__(self, attrs=None):
        super().__init__({"size": 18, **(attrs or {})})

    def format_value(self, value):
        if isinstance(value, datetime.datetime):
            if timezone.is_aware(value):
                value = timezone.localtime(value)
            return f"{jalali_text(value.date())} {value:%H:%M}"
        return super().format_value(value)

    def value_from_datadict(self, data, files, name):
        raw = data.get(name)
        if not raw:
            return raw
        parts = str(raw).translate(LATIN).strip().split()
        time = parts[1] if len(parts) > 1 else "00:00"
        day = parse_date(parts[0]) if parts else None
        if day is None or len(parts) > 2:
            return raw
        return f"{day.isoformat()} {time}"


class JalaliDateField(forms.DateField):
    widget = JalaliDateInput
