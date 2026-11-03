"""Branding for the Wagtail admin: logo, favicon and name from the admin settings, with built-in fallbacks."""

from django import template
from django.templatetags.static import static

register = template.Library()


def _rendition_url(image, spec):
    try:
        return image.get_rendition(spec).url
    except Exception:  # a missing or broken image file must never break the admin
        return ""


@register.simple_tag(takes_context=True)
def admin_brand(context):
    from core.models import SeoSettings, SiteSettings

    request = context.get("request")
    site = SiteSettings.load(request_or_site=request)
    seo = SeoSettings.load(request_or_site=request)
    logo_light = site.logo_light and _rendition_url(site.logo_light, "height-160|format-png")
    logo = site.logo and _rendition_url(site.logo, "height-160|format-png")
    icon = seo.site_icon and _rendition_url(seo.site_icon, "fill-64x64|format-png")
    return {
        "name": site.site_name,
        "logo_light": logo_light or static("img/logo-white.png"),  # on the navy sidebar
        "logo": logo or static("img/logo-navy.png"),  # on white (sign-in page)
        "favicon": icon or static("img/app-icon-192.png"),
    }
