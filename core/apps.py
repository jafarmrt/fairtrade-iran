from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "هسته"

    def ready(self):
        from . import throttle  # noqa: F401  (connects the sign-in signals)
        from django.db import models
        from wagtail.admin.forms.models import register_form_field_override

        from .widgets import JalaliDateInput, JalaliDateTimeInput

        # Every date and date-time in the Wagtail admin (snippets, settings, page "go live" schedule) is Jalali.
        register_form_field_override(models.DateField, override={"widget": JalaliDateInput})
        register_form_field_override(models.DateTimeField, override={"widget": JalaliDateTimeInput})
