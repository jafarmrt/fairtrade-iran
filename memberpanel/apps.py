from django.apps import AppConfig


class MemberPanelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "memberpanel"
    verbose_name = "پنل اعضا"

    def ready(self):
        from . import signals  # noqa: F401
