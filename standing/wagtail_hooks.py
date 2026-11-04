from django.template.loader import render_to_string
from django.utils import timezone
from wagtail import hooks
from wagtail.admin.ui.components import Component
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from core.admin_columns import MoneyColumn
from members.models import Member

from .models import Dues, DuesPayment
from .services import COMMISSION, SECRETARIAT, user_bodies

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


class StandingPanel(Component):
    name = "standing_pending"
    order = 60

    def __init__(self, request):
        self.request = request

    def render_html(self, parent_context=None):
        bodies = user_bodies(self.request.user)
        if not bodies:
            return ""
        today = timezone.localdate()
        items = []
        if SECRETARIAT in bodies:
            pending = DuesPayment.objects.filter(status=DuesPayment.Status.PENDING).count()
            if pending:
                items.append((pending, "رسید حق عضویت در انتظار بررسی", "pending"))
            overdue = Dues.objects.filter(status=Dues.Status.UNPAID, due_date__lt=today).count()
            if overdue:
                items.append((overdue, "حق عضویت گذشته از مهلت", "overdue"))
        if bodies & {SECRETARIAT, COMMISSION}:
            ended = Member.objects.filter(status=Member.SUSPENDED, suspended_until__lte=today).count()
            if ended:
                items.append((ended, "عضو با مدت تعلیق تمام‌شده (رفع تعلیق یا لغو)", "ended"))
        if not items:
            return ""
        return render_to_string("standing/admin/dashboard_panel.html", {"items": items}, request=self.request)


@hooks.register("construct_homepage_panels")
def add_standing_panel(request, panels):
    panels.append(StandingPanel(request))
