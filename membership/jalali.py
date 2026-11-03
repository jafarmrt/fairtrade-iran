"""
Small Gregorian -> Jalali (Solar Hijri) converter, so dates show the way
Persian readers expect without an extra dependency.
"""

import datetime

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def to_jalali(gy, gm, gd):
    """Return (year, month, day) in the Jalali calendar."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100)
        + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    )
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def persian_digits(value):
    return str(value).translate(PERSIAN_DIGITS)


def as_date(value):
    if isinstance(value, datetime.datetime):
        from django.utils import timezone

        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    return value


def format_jalali(value, long=True):
    value = as_date(value)
    if not value:
        return ""
    y, m, d = to_jalali(value.year, value.month, value.day)
    if long:
        return persian_digits(f"{d} {MONTHS[m - 1]} {y}")
    return persian_digits(f"{y}/{m:02d}/{d:02d}")


def jalali_year(value):
    value = as_date(value)
    return to_jalali(value.year, value.month, value.day)[0]


def to_gregorian(jy, jm, jd):
    """Return a datetime.date for a Jalali (year, month, day). Algorithm from jalaali-js (MIT)."""
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd
    days += (jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    month_days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 12 and gd > month_days[gm]:
        gd -= month_days[gm]
        gm += 1
    return datetime.date(gy, gm + 1, gd)
