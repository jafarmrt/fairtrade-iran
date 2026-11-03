from django.template.loader import get_template
from django.utils.html import format_html
from wagtail import hooks
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.admin.viewsets.model import ModelViewSet

from .models import Complaint


class AttachmentPanel(FieldPanel):
    """Read-only link to the attachment through the commission-only download view."""

    class BoundPanel(FieldPanel.BoundPanel):
        def get_read_only_context_data(self):
            context = super().get_read_only_context_data()
            if self.instance.attachment:
                context["display_value"] = format_html(
                    '<a href="{}">دانلود پیوست</a>', self.instance.attachment_url()
                )
            else:
                context["display_value"] = "—"
            context["rendered_field"] = get_template(self.panel.read_only_output_template_name).render(context)
            return context


class ComplaintViewSet(ModelViewSet):
    """
    Complaints are visible only to users with the complaint permissions,
    which seed_content gives to the Supervisory Commission group alone.
    Complaints arrive from the website, so there is no 'add' view in practice.
    """

    model = Complaint
    icon = "warning"
    menu_label = "شکایات"
    menu_order = 250
    add_to_admin_menu = True
    copy_view_enabled = False
    list_display = ["tracking_code", "subject_of_complaint", "category", "status", "created_at"]
    list_filter = ["status", "category"]
    search_fields = ["tracking_code", "subject_of_complaint", "name", "description"]
    panels = [
        MultiFieldPanel([
            FieldPanel("tracking_code", read_only=True),
            FieldPanel("created_at", read_only=True),
            FieldPanel("name", read_only=True),
            FieldPanel("email", read_only=True),
            FieldPanel("phone", read_only=True),
            FieldPanel("relation", read_only=True),
        ], heading="شاکی"),
        MultiFieldPanel([
            FieldPanel("subject_of_complaint", read_only=True),
            FieldPanel("category", read_only=True),
            FieldPanel("description", read_only=True),
            AttachmentPanel("attachment", read_only=True),
        ], heading="شکایت"),
        MultiFieldPanel([
            FieldPanel("status"),
            FieldPanel("commission_notes"),
        ], heading="رسیدگی کمیسیون"),
    ]


complaint_viewset = ComplaintViewSet("complaints")


@hooks.register("register_admin_viewset")
def register_complaint_viewset():
    return complaint_viewset
