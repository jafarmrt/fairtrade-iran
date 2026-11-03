from django.http import Http404, HttpResponse
from django.shortcuts import redirect

from core.models import SeoSettings

PRIVATE_PATHS = [
    "/admin/",
    "/fa/panel/",
    "/en/panel/",
    "/fa/search/",
    "/en/search/",
]


def robots_txt(request):
    seo = SeoSettings.load(request_or_site=request)
    lines = ["User-agent: *"]
    if seo.allow_indexing:
        lines += [f"Disallow: {path}" for path in PRIVATE_PATHS]
        lines += [line.strip() for line in seo.robots_extra.splitlines() if line.strip()]
        lines += ["", f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}"]
    else:
        lines.append("Disallow: /")
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def favicon(request):
    seo = SeoSettings.load(request_or_site=request)
    if not seo.site_icon:
        raise Http404
    return redirect(seo.site_icon.get_rendition("fill-32x32|format-png").url, permanent=False)
