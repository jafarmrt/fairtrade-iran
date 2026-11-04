"""Columns for admin listings that show values the way people read them."""

import django_filters
from django.db.models import Q
from wagtail.admin.ui.tables import BooleanColumn, Column
from wagtail.admin.widgets import BooleanRadioSelect

from core import money


class MoneyColumn(Column):
    """
    A rial field shown as '۲٬۴۰۰٬۰۰۰ ریال' instead of '2400000': in rials, like the edit form
    that asks for it (the site may show the same price in tomans).
    """

    def __init__(self, name, label=None, **kwargs):
        def accessor(obj):
            value = getattr(obj, name)
            return money.amount(value, mode=money.RIAL) if value not in (None, "") else "—"

        super().__init__(name, label=label, accessor=accessor, sort_key=name, classname="ft-nowrap", **kwargs)


class EnglishColumn(BooleanColumn):
    """
    ✓ when the English translation (``name_en``) is filled in, ✗ when it is empty. Items
    without it are hidden on the English site, so this tells the editor what is missing
    without a column of Latin text in a Persian list.
    """

    def __init__(self, name="name_en", label="ترجمهٔ انگلیسی", **kwargs):
        super().__init__(name, label=label, accessor=lambda obj: bool(getattr(obj, name, "")), **kwargs)


def english_filter(field="name_en"):
    """A «ترجمهٔ انگلیسی» filter for a WagtailFilterSet: with / without the English name."""

    def filter_english(queryset, name, value):
        if value is None:
            return queryset
        empty = Q(**{field: ""}) | Q(**{f"{field}__isnull": True})
        return queryset.exclude(empty) if value else queryset.filter(empty)

    widget = BooleanRadioSelect()
    widget.choices = [("", "همه"), ("true", "دارد"), ("false", "ندارد")]
    return django_filters.BooleanFilter(label="ترجمهٔ انگلیسی", method=filter_english, widget=widget)
