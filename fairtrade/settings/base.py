"""
Base settings for the Fair Trade House of Iran website.

Everything that differs between machines (secret key, database, hosts,
email) comes from environment variables, so the same code runs on a
server inside Iran or abroad without changes.
"""

import os

import dj_database_url
from django.utils.translation import gettext_lazy as _

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(PROJECT_DIR)


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# Application definition

INSTALLED_APPS = [
    # Project apps
    "core",
    "sms",
    "home",
    "pages",
    "search",
    "news",
    "archive",
    "contact",
    "members",
    "products",
    "membership",
    "memberpanel",
    "standing",
    "appeals",
    # Wagtail
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.settings",
    "wagtail.contrib.routable_page",
    "wagtail.contrib.simple_translation",
    "wagtail.locales",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "fairtrade.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(PROJECT_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wagtail.contrib.settings.context_processors.settings",
                "core.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "fairtrade.wsgi.application"


# Database: DATABASE_URL (e.g. postgres://user:pass@db:5432/fairtrade),
# falling back to a local SQLite file for development.

DATABASES = {
    "default": dj_database_url.config(
        default="sqlite:///" + os.path.join(BASE_DIR, "db.sqlite3"),
        conn_max_age=600,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalisation: Persian is the default, English the second language.

LANGUAGE_CODE = "fa"
LANGUAGES = [
    ("fa", "فارسی"),
    ("en", "English"),
]
WAGTAIL_I18N_ENABLED = True
WAGTAIL_CONTENT_LANGUAGES = LANGUAGES
WAGTAILADMIN_PERMITTED_LANGUAGES = LANGUAGES
LOCALE_PATHS = [os.path.join(BASE_DIR, "locale")]

TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True


# Static and media files

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]
STATICFILES_DIRS = [os.path.join(PROJECT_DIR, "static")]
STATIC_ROOT = os.environ.get("STATIC_ROOT", os.path.join(BASE_DIR, "staticfiles"))
STATIC_URL = "/static/"

MEDIA_ROOT = os.environ.get("MEDIA_ROOT", os.path.join(BASE_DIR, "media"))
MEDIA_URL = "/media/"

# Files people send with membership applications (IDs, receipts, licences)
# are kept outside MEDIA_ROOT and are only downloadable by staff.
PRIVATE_MEDIA_ROOT = os.environ.get(
    "PRIVATE_MEDIA_ROOT", os.path.join(BASE_DIR, "private_media")
)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024


# Wagtail

WAGTAIL_SITE_NAME = "خانه تجارت عادلانه ایران"
WAGTAILADMIN_BASE_URL = os.environ.get("SITE_URL", "http://localhost:8000")
WAGTAILSEARCH_BACKENDS = {"default": {"BACKEND": "wagtail.search.backends.database"}}
WAGTAILDOCS_EXTENSIONS = ["csv", "docx", "odt", "pdf", "pptx", "rtf", "txt", "xlsx", "zip", "jpg", "png"]
# Documents are served through Django so that collection privacy
# (members only, board only, commission only) is always enforced.
WAGTAILDOCS_SERVE_METHOD = "serve_view"
# Our document model adds English title/description and keeps the files
# under PRIVATE_MEDIA_ROOT, so they cannot be fetched from /media/ directly.
WAGTAILDOCS_DOCUMENT_MODEL = "archive.ArchiveDocument"


# Email

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@localhost")

# SMS: provider, sender line and texts are set in the admin (Settings > تنظیمات پیامک).
# SMS_API_KEY keeps the provider key out of the database if you prefer;
# SMS_BACKEND (a dotted path) forces one backend, e.g. sms.backends.ConsoleBackend.
SMS_API_KEY = os.environ.get("SMS_API_KEY", "")
SMS_BACKEND = os.environ.get("SMS_BACKEND", "")

LOGIN_URL = "/admin/login/"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "memberpanel.backends.EmailBackend",  # sign in with e-mail as well as username
]
