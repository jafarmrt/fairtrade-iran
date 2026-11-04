"""
Persian first, whatever language the browser asks for.

Django's LocaleMiddleware picks the language of a page without a /fa/ or /en/ prefix from
the browser's Accept-Language header. Most computers in Iran run Windows or Android in
English, so the admin (/admin/, which has no language prefix), its sign-in page and every
link without a prefix (/, /panel/) opened in English and left to right. Here:

* the admin and the sign-in steps (two-factor code) are always Persian; an editor who
  wants English picks it in «حساب کاربری ← زبان» and Wagtail then switches for that user;
* a page with a /fa/ or /en/ prefix is in that language;
* any other address is in Persian, unless the visitor chose a language before
  (Django's language cookie). The site's language switcher links to /en/ for English.
"""

from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.urls import reverse
from django.utils import translation

# Paths that belong to the admin and always start in Persian.
ADMIN_PATHS = ("/two-factor/",)


def _admin_prefixes():
    return (reverse("wagtailadmin_home"),) + ADMIN_PATHS


def is_admin_path(path):
    return path.startswith(_admin_prefixes())


def _language_from_cookie(request):
    lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
    if not lang:
        return None
    try:
        return translation.get_supported_language_variant(lang)
    except LookupError:
        return None


class PersianFirstLocaleMiddleware(LocaleMiddleware):
    def process_request(self, request):
        path = request.path_info
        if is_admin_path(path):
            language = settings.LANGUAGE_CODE
        else:
            language = (
                translation.get_language_from_path(path)
                or _language_from_cookie(request)
                or settings.LANGUAGE_CODE
            )
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

    def process_response(self, request, response):
        # A missing admin page is a 404 of the admin, not a hint to try /fa/admin/… on the site.
        if is_admin_path(request.path_info):
            response.headers.setdefault("Content-Language", translation.get_language())
            return response
        return super().process_response(request, response)
