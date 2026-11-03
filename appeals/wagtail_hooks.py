from django.db import transaction
from django.template.loader import get_template
from django.utils.html import format_html
from wagtail import hooks
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.admin.views.generic import EditView

from . import notifications
from .models import Appeal


class AttachmentPanel(FieldPanel):
    """Read-only link to the attachment through the permission-checked download view."""

    class BoundPanel(FieldPanel.BoundPanel):
        def get_read_only_context_data(self):
            context = super().get_read_only_context_data()
            if self.instance.attachment:
                context["display_value"] = format_html('<a href="{}">دانلود پیوست</a>', self.instance.attachment_url())
            else:
                context["display_value"] = "—"
            context["rendered_field"] = get_template(self.panel.read_only_output_template_name).render(context)
            return context


class AppealEditView(EditView):
    def save_instance(self):
        changed = self.form.instance.status_changed
        instance = super().save_instance()
        if changed:
            transaction.on_commit(lambda: notifications.status_changed(instance))
        return instance


class AppealViewSet(ModelViewSet):
    """
    Appeals are visible only to users with the appeal permissions, which
    seed_content gives to the «دبیر مجمع» group (secretary and deputy).
    Members file appeals from the member panel, so there is no 'add' view in practice.
    """

    model = Appeal
    icon = "pick"
    menu_label = "اعتراض‌ها"
    menu_order = 260
    add_to_admin_menu = True
    copy_view_enabled = False
    edit_view_class = AppealEditView
    list_display = ["tracking_code", "member_name", "decision", "status", "submitted_at", "decide_by"]
    list_filter = ["status", "decision"]
    search_fields = ["tracking_code", "member_name", "grounds"]
    panels = [
        MultiFieldPanel([
            FieldRowPanel([FieldPanel("tracking_code", read_only=True), FieldPanel("submitted_at", read_only=True)]),
            FieldPanel("member", read_only=True),
            FieldPanel("application", read_only=True),
            FieldPanel("standing_decision", read_only=True),
            FieldRowPanel([FieldPanel("email", read_only=True), FieldPanel("phone", read_only=True)]),
        ], heading="معترض"),
        MultiFieldPanel([
            FieldRowPanel([FieldPanel("decision", read_only=True), FieldPanel("decision_body", read_only=True)]),
            FieldRowPanel([FieldPanel("decision_date", read_only=True),
                           FieldPanel("decision_reference", read_only=True)]),
            FieldPanel("grounds", read_only=True),
            AttachmentPanel("attachment", read_only=True),
        ], heading="اعتراض"),
        MultiFieldPanel([
            FieldRowPanel([FieldPanel("status"), FieldPanel("decide_by")]),
            FieldPanel("handled_by_deputy"),
            FieldPanel("hearing_date"),
            FieldPanel("ruling"),
            FieldPanel("ruled_on", read_only=True),
            FieldPanel("secretary_notes"),
        ], heading="رسیدگی دبیر مجمع",
            help_text="با تغییر وضعیت، به عضو ایمیل زده می‌شود و وضعیت و متن رأی را در پنل خود می‌بیند. رأی دبیر مجمع قطعی است."),
    ]


appeal_viewset = AppealViewSet("appeals")


@hooks.register("register_admin_viewset")
def register_appeal_viewset():
    return appeal_viewset
