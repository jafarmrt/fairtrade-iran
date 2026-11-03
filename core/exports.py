"""
Spreadsheet exports for the admin: CSV files that Excel opens with Persian
text intact (UTF-8 with a byte-order mark), with Jalali dates written as
1405/08/12 so they sort correctly, and amounts in rials as plain numbers.
Also the Jalali month arithmetic the monthly reports need.
"""

import csv
import datetime

from django.http import HttpResponse
from django.utils import timezone

from membership.jalali import MONTHS, to_gregorian, to_jalali


def jalali_stamp(value, with_time=True):
    """'1405/08/12 14:30' for a datetime, '1405/08/12' for a date, '' for None."""
    if not value:
        return ""
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        y, m, d = to_jalali(value.year, value.month, value.day)
        return f"{y}/{m:02d}/{d:02d}" + (f" {value:%H:%M}" if with_time else "")
    y, m, d = to_jalali(value.year, value.month, value.day)
    return f"{y}/{m:02d}/{d:02d}"


def csv_response(filename, header, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return response


# ---- Jalali months ----

def jalali_today():
    today = timezone.localdate()
    return to_jalali(today.year, today.month, today.day)


def month_name(jm):
    return MONTHS[jm - 1]


def add_months(jy, jm, n):
    index = jy * 12 + (jm - 1) + n
    return index // 12, index % 12 + 1


def month_bounds(jy, jm):
    """Aware datetimes [start, end) of a Jalali month, in the site's time zone."""
    start = to_gregorian(jy, jm, 1)
    end = to_gregorian(*add_months(jy, jm, 1), 1)
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime.datetime.combine(start, datetime.time.min), tz),
            timezone.make_aware(datetime.datetime.combine(end, datetime.time.min), tz))


def parse_month(value):
    """'1405-08' or '1405/08' (any digits) as (1405, 8), or None."""
    from core.iran import latin_digits

    parts = latin_digits(value or "").replace("/", "-").split("-")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return None
    jy, jm = int(parts[0]), int(parts[1])
    return (jy, jm) if 1300 <= jy <= 1500 and 1 <= jm <= 12 else None
