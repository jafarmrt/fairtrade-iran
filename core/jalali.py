"""
Gregorian to Jalali (Solar Hijri) conversion, so Persian pages show dates
the way Iranian readers expect, without an extra dependency.
Algorithm from jalaali-js (MIT), valid for years 1–3177 AD.
"""

import datetime

MONTHS_FA = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_persian_digits(value):
    return str(value).translate(PERSIAN_DIGITS)


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def format_jalali(value, with_time=False):
    """'۱۱ آبان ۱۴۰۵' (and ', ساعت ۱۸:۳۰' when with_time) for a date or datetime."""
    if isinstance(value, datetime.datetime):
        from django.utils import timezone

        if timezone.is_aware(value):
            value = timezone.localtime(value)
    jy, jm, jd = gregorian_to_jalali(value.year, value.month, value.day)
    text = f"{jd} {MONTHS_FA[jm - 1]} {jy}"
    if with_time and isinstance(value, datetime.datetime):
        text += f"، ساعت {value:%H:%M}"
    return to_persian_digits(text)
