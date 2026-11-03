"""<head> tags and the install banner of the phone version (core/pwa.py)."""

from django import template
from django.urls import reverse

from core import pwa as pwa_lib
from core.models import PwaSettings, SeoSettings

register = template.Library()


@register.inclusion_tag("core/pwa/head.html", takes_context=True)
def pwa_head(context):
    request = context["request"]
    pwa = PwaSettings.load(request_or_site=request)
    if not pwa.enabled:
        return {"enabled": False}
    seo = SeoSettings.load(request_or_site=request)
    return {
        "enabled": True,
        "pwa": pwa,
        "manifest_url": reverse("manifest"),
        "short_name": pwa.tr("short_name"),
        # seo_head already gives the iPhone an icon when a site icon is uploaded.
        "touch_icon": "" if seo.site_icon and not pwa.icon else pwa_lib.touch_icon_url(pwa, seo),
    }


@register.inclusion_tag("core/pwa/body.html", takes_context=True)
def pwa_body(context):
    request = context["request"]
    pwa = PwaSettings.load(request_or_site=request)
    return {
        "pwa": pwa,
        "IS_EN": context.get("IS_EN"),
        "CSP_NONCE": context.get("CSP_NONCE", ""),
    }
