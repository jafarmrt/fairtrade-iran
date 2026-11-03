from wagtail.admin.viewsets.base import ViewSetGroup
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .admin_views import SmsAdminViewSet
from .models import SmsTemplate


class SmsTemplateViewSet(SnippetViewSet):
    model = SmsTemplate
    icon = "mail"
    menu_label = "متن‌های پیامک"
    list_display = ["__str__", "audience", "active"]
    list_filter = ["active"]
    search_fields = ["text", "text_en"]


class SmsGroup(ViewSetGroup):
    menu_label = "پیامک"
    menu_name = "sms"  # the order of the main menu is set in core/wagtail_hooks.py
    menu_icon = "mail"
    items = (SmsTemplateViewSet, SmsAdminViewSet)


register_snippet(SmsGroup)
