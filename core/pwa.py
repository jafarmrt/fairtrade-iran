"""
The installable phone version of the site (Progressive Web App).

* /<lang>/manifest.webmanifest: name, icons and colours from PwaSettings (admin > Settings).
* /sw.js: the service worker. It keeps the site's own static files and public pictures, shows
  /<lang>/offline/ when there is no connection, and keeps a copy of public pages only when the
  server marks them safe to keep (PwaCacheHintMiddleware below). Member panel, admin, forms,
  cart, checkout and payment pages are never kept.
* When PWA is switched off in the admin, /sw.js becomes a worker that empties its caches and
  unregisters itself, so phones that installed the app go back to the plain site.
"""

import hashlib
import json

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import override

from core.models import PwaSettings, SeoSettings, SiteSettings

# Bump when sw.js logic changes, so installed workers update even if no setting changed.
SW_REVISION = "1"

CACHE_HINT_HEADER = "X-PWA-Cache"

# Never kept, and the worker does not even look at them (network only). The language-prefixed
# ones are listed for both languages.
NEVER_CACHE_PREFIXES = (
    "/admin/",
    "/django-admin/",
    "/documents/",
    "/two-factor/",
    "/i18n/",
    "/pay/",
    "/complaint-files/",
    "/appeal-files/",
    "/sw.js",
)
NEVER_CACHE_LANG_PREFIXES = ("panel/", "search/")

PRECACHE_STATIC = (
    "css/fairtrade.css",
    "fonts/Vazirmatn-Regular.woff2",
    "fonts/Vazirmatn-Medium.woff2",
    "fonts/Vazirmatn-Bold.woff2",
    "img/logo-navy.png",
    "img/logo-white.png",
    "img/app-icon-192.png",
)

DEFAULT_ICONS = (
    ("img/app-icon-192.png", 192, "any"),
    ("img/app-icon-512.png", 512, "any"),
    ("img/app-icon-maskable-512.png", 512, "maskable"),
)


def languages():
    return [code for code, _name in settings.LANGUAGES]


def never_cache_prefixes():
    prefixes = list(NEVER_CACHE_PREFIXES)
    for lang in languages():
        prefixes += [f"/{lang}/{p}" for p in NEVER_CACHE_LANG_PREFIXES]
    return prefixes


def _rendition(image, spec):
    try:
        return image.get_rendition(spec)
    except Exception:  # a missing source file must never break the manifest
        return None


def icons(pwa, seo):
    """Manifest icon entries: the PWA icon, else the site icon, else the bundled default."""
    def entry(src, width, height, purpose):
        return {"src": src, "sizes": f"{width}x{height}", "type": "image/png", "purpose": purpose}

    result = []
    source = pwa.icon or seo.site_icon
    if source:
        for size in (192, 512):
            r = _rendition(source, f"fill-{size}x{size}|format-png")
            if r:
                result.append(entry(r.url, r.width, r.height, "any"))
    default_used = not result
    if default_used:
        result += [entry(static(path), size, size, purpose) for path, size, purpose in DEFAULT_ICONS
                   if purpose == "any"]
    maskable = _rendition(pwa.maskable_icon, "fill-512x512|format-png") if pwa.maskable_icon else None
    if maskable:
        result.append(entry(maskable.url, maskable.width, maskable.height, "maskable"))
    elif default_used:
        # Only the bundled icon has a known safe zone; an uploaded one is not offered as maskable.
        result += [entry(static(path), size, size, purpose) for path, size, purpose in DEFAULT_ICONS
                   if purpose == "maskable"]
    return result


def touch_icon_url(pwa, seo):
    """Icon for the iPhone home screen."""
    source = pwa.icon or seo.site_icon
    if source:
        r = _rendition(source, "fill-180x180|format-png")
        if r:
            return r.url
    return static("img/app-icon-180.png")


def manifest(request):
    pwa = PwaSettings.load(request_or_site=request)
    if not pwa.enabled:
        raise Http404
    site = SiteSettings.load(request_or_site=request)
    seo = SeoSettings.load(request_or_site=request)
    lang = (request.LANGUAGE_CODE or "fa")[:2]
    data = {
        "id": f"/{lang}/",
        "name": pwa.tr("app_name") or site.tr("site_name"),
        "short_name": pwa.tr("short_name") or site.tr("site_name"),
        "description": pwa.tr("description") or seo.tr("default_description"),
        "lang": lang,
        "dir": "rtl" if lang == "fa" else "ltr",
        "start_url": f"/{lang}/",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "theme_color": pwa.theme_color,
        "background_color": pwa.background_color,
        "categories": ["shopping", "business"],
        "icons": icons(pwa, seo),
    }
    response = JsonResponse(data, json_dumps_params={"ensure_ascii": False, "indent": 2})
    response["Content-Type"] = "application/manifest+json; charset=utf-8"
    response["Cache-Control"] = "public, max-age=3600"
    return response


def offline_urls():
    urls = {}
    for lang in languages():
        with override(lang):
            urls[lang] = reverse("offline")
    return urls


def version(pwa, seo):
    """Changes whenever anything the worker caches or shows may have changed."""
    parts = [SW_REVISION, static("css/fairtrade.css"), str(seo.site_icon_id)]
    parts += [str(getattr(pwa, f.attname)) for f in pwa._meta.concrete_fields]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def service_worker(request):
    pwa = PwaSettings.load(request_or_site=request)
    if pwa.enabled:
        seo = SeoSettings.load(request_or_site=request)
        offline = offline_urls()
        config = {
            "version": version(pwa, seo),
            "offline": offline,
            "precache": list(offline.values()) + [static(p) for p in PRECACHE_STATIC],
            "never": never_cache_prefixes(),
            "staticPrefix": settings.STATIC_URL,
            "staticImmutable": not settings.DEBUG,
            "imagePrefix": settings.MEDIA_URL.rstrip("/") + "/images/",
            "cachePages": pwa.cache_pages,
            "hintHeader": CACHE_HINT_HEADER,
        }
        template = "core/pwa/sw.js"
    else:
        config = {}
        template = "core/pwa/sw-off.js"
    response = render(request, template, {"config": json.dumps(config, ensure_ascii=False)},
                      content_type="application/javascript; charset=utf-8")
    # Browsers check for a new worker on every visit; never let a proxy keep an old one.
    response["Cache-Control"] = "no-cache, max-age=0"
    return response


def offline(request):
    pwa = PwaSettings.load(request_or_site=request)
    if not pwa.enabled:
        raise Http404
    return render(request, "core/pwa/offline.html", {"pwa": pwa})


class PwaCacheHintMiddleware:
    """
    Marks responses the service worker may keep for offline reading: public HTML pages that a
    signed-out visitor sees the same way everyone else does. Anything with a form (CSRF token),
    a session (cart, sign-in), a one-off message or a private Cache-Control is left unmarked.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if self.cacheable(request, response):
            response[CACHE_HINT_HEADER] = "page"
        return response

    @staticmethod
    def cacheable(request, response):
        if request.method != "GET" or response.status_code != 200 or response.streaming:
            return False
        if not response.get("Content-Type", "").startswith("text/html"):
            return False
        if request.path.startswith(tuple(never_cache_prefixes())):
            return False
        cache_control = response.get("Cache-Control", "").lower()
        if "private" in cache_control or "no-store" in cache_control:
            return False
        if response.cookies:
            return False
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return False
        if request.META.get("CSRF_COOKIE_NEEDS_UPDATE"):
            return False
        session = getattr(request, "session", None)
        if session is not None and not session.is_empty():
            return False
        messages = getattr(request, "_messages", None)
        if messages is not None and getattr(messages, "used", False):
            return False
        return True
