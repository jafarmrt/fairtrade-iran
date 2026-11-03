from .base import *  # noqa: F401,F403

DEBUG = True

# Development only. Production reads SECRET_KEY from the environment.
SECRET_KEY = "django-insecure-dev-only-key-change-me"

ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
SMS_BACKEND = "sms.backends.ConsoleBackend"  # never spend real SMS credit from a dev copy

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

try:
    from .local import *  # noqa: F401,F403
except ImportError:
    pass
