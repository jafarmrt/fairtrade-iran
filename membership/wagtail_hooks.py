from django.template.loader import render_to_string
from django.utils import timezone
from wagtail import hooks
from wagtail.admin.ui.components import Component
from wagtail.admin.viewsets.base import ViewSetGroup
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .admin_views import ApplicationViewSet, files_needing_action
from .models import ApplicationQuestion, Certificate, EmailTemplate


class QuestionViewSet(SnippetViewSet):
    model = ApplicationQuestion
    icon = "form"
    menu_label = "پرسش‌های فرم"
    list_display = ["label", "types_display", "field_type", "required", "sort_order", "active"]
    list_filter = ["field_type", "active", "for_producer", "for_institution", "for_network", "for_individual"]
    search_fields = ["label", "label_en"]
    ordering = ["sort_order", "id"]


class EmailTemplateViewSet(SnippetViewSet):
    model = EmailTemplate
    icon = "mail"
    menu_label = "ایمیل‌ها"
    list_display = ["__str__", "subject", "active"]


class CertificateViewSet(SnippetViewSet):
    model = Certificate
    icon = "doc-full"
    menu_label = "گواهی‌ها"
    list_display = ["number", "name", "member_type", "issued_on", "valid_until", "revoked"]
    list_filter = ["member_type", "revoked"]
    search_fields = ["number", "name", "name_en"]


class MembershipGroup(ViewSetGroup):
    menu_label = "عضویت"
    menu_icon = "group"
    menu_order = 150
    items = (ApplicationViewSet, QuestionViewSet, EmailTemplateViewSet, CertificateViewSet)


register_snippet(MembershipGroup)


class PendingApplicationsPanel(Component):
    name = "membership_pending"
    order = 50

    def __init__(self, request):
        self.request = request

    def render_html(self, parent_context=None):
        files = list(files_needing_action(self.request.user)[:10])
        if not files:
            return ""
        return render_to_string("membership/admin/dashboard_panel.html", {
            "applications": files,
            "today": timezone.localdate(),
        }, request=self.request)


@hooks.register("construct_homepage_panels")
def add_pending_panel(request, panels):
    panels.append(PendingApplicationsPanel(request))
