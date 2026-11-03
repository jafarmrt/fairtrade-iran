from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "هسته"

    def ready(self):
        from . import throttle  # noqa: F401  (connects the sign-in signals)
