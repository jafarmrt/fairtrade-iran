from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from core.admin_columns import MoneyColumn

from .models import Dues

# «وضعیت اعضا و حق عضویت» (admin_views.StandingViewSet) is registered in the «عضویت» menu group
# by membership/wagtail_hooks.py.


class DuesViewSet(SnippetViewSet):
    """Plain list of all dues, for export and corrections."""

    model = Dues
    icon = "doc-full"
    menu_label = "فهرست حق عضویت‌ها"
    add_to_admin_menu = False
    list_display = ["member", "year", MoneyColumn("amount", label="مبلغ"), "due_date", "status", "warned_on", "paid_on"]
    list_filter = ["status", "year"]
    list_export = ["member", "year", "amount", "period_start", "due_date", "status", "warned_on", "paid_on"]
    search_fields = ["member__name"]


register_snippet(DuesViewSet)

# Waiting receipts, overdue dues and ended suspensions are counted on the dashboard in
# «کارهای منتظر شما» (core.admin_views.pending_for).
