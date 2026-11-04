"""Columns for admin listings that show values the way people read them."""

from wagtail.admin.ui.tables import Column

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
