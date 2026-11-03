from django.apps import AppConfig


class SmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sms"
    verbose_name = "پیامک"

    def ready(self):
        # Each app describes its own SMS events in an `sms_events.py` module.
        from django.utils.module_loading import autodiscover_modules

        autodiscover_modules("sms_events")
