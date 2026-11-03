from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "هسته"

    def ready(self):
        from django.db import models
        from wagtail.admin.forms.models import register_form_field_override

        from . import jalali_dates
        from . import throttle  # noqa: F401  (connects the sign-in signals)
        from .widgets import JalaliDateInput, JalaliDateTimeInput

        # Dates shown on Persian pages and in the admin (listings, history, "locked at") are Jalali.
        jalali_dates.install()

        # Every date and date-time in the Wagtail admin (snippets, settings, page "go live" schedule) is Jalali.
        register_form_field_override(models.DateField, override={"widget": JalaliDateInput})
        register_form_field_override(models.DateTimeField, override={"widget": JalaliDateTimeInput})
