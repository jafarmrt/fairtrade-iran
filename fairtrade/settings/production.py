import os

from .base import *  # noqa: F401,F403
from .base import env_list

DEBUG = False

SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if os.environ.get("SPACE_HOST"):  # Hugging Face Spaces: <user>-<space>.hf.space
    ALLOWED_HOSTS.append(os.environ["SPACE_HOST"])
    CSRF_TRUSTED_ORIGINS.append("https://" + os.environ["SPACE_HOST"])

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_HTTPS = os.environ.get("USE_HTTPS", "1") == "1"
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"  # Wagtail's page preview needs frames from the same site
# nginx sends HSTS; set SECURE_HSTS_SECONDS too if the site runs without the bundled nginx.
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.environ.get("CACHE_DIR", "/tmp/fairtrade-cache"),
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}

try:
    from .local import *  # noqa: F401,F403
except ImportError:
    pass
