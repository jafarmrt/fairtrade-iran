from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"
    verbose_name = "پرداخت آنلاین"

    def ready(self):
        from . import purposes  # noqa: F401  registers application_fee, dues and order
