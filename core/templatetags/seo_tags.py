"""
Search-engine and link-preview tags for <head>: description, canonical URL,
hreflang alternates, Open Graph / Twitter cards and schema.org JSON-LD.

Everything is taken from the page or object being shown, falling back to
SeoSettings (edited in the admin under Settings).
"""

import json

from django import template
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.text import Truncator
from wagtail.models import Page

from core.models import SeoSettings, SiteSettings, is_english

register = template.Library()

DESCRIPTION_LENGTH = 200


def _absolute(request, url):
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return request.build_absolute_uri(url)


def _rendition_url(request, image, spec):
    if not image:
        return ""
    try:
        return _absolute(request, image.get_rendition(spec).url)
    except Exception:  # a missing source file must never break the page
        return ""


def _clean(text):
    text = " ".join(strip_tags(str(text or "")).split())
    return Truncator(text).chars(DESCRIPTION_LENGTH)


def _subject(context):
    """The product or member a routable detail view shows, if any."""
    if not context.get("routable_suffix"):
        return None
    for key in ("product", "member"):
        obj = context.get(key)
        if obj is not None and hasattr(obj, "tr"):
            return obj
    return None


def _page_image(page):
    for name in ("cover_image", "hero_image", "feed_image", "image"):
        image = getattr(page, name, None)
        if image is not None and hasattr(image, "get_rendition"):
            return image
    return None


def _page_description(page):
    if page.search_description:
        return page.search_description
    for name in ("intro", "hero_text"):
        value = getattr(page, name, "")
        if value:
            return value
    return ""


def alternates(context):
    """[(language_code, absolute_url)] for this page in every live language."""
    request = context["request"]
    page = context.get("page")
    if not isinstance(page, Page):
        return []
    subject = _subject(context)
    suffix = context.get("routable_suffix") or ""
    links = []
    for translation in page.get_translations(inclusive=True).live().select_related("locale"):
        lang = translation.locale.language_code
        if subject is not None and lang == "en" and not getattr(subject, "name_en", ""):
            continue
        url = translation.get_url(request)
        if url:
            url = _absolute(request, url)
            links.append((lang, url + suffix))
    return links if len(links) > 1 else []


@register.inclusion_tag("core/seo_head.html", takes_context=True)
def seo_head(context):
    request = context["request"]
    seo = SeoSettings.load(request_or_site=request)
    site = SiteSettings.load(request_or_site=request)
    english = is_english()
    site_name = site.tr("site_name")
    page = context.get("page") if isinstance(context.get("page"), Page) else None
    subject = _subject(context)

    title = site_name
    description = ""
    image = None
    og_type = "website"
    if subject is not None:
        title = subject.tr("name")
        description = subject.tr("summary")
        image = getattr(subject, "main_image", None) or getattr(subject, "cover_image", None) \
            or getattr(subject, "logo", None)
        og_type = "product" if subject._meta.model_name == "product" else "profile"
    elif page is not None:
        page = page.specific
        title = page.seo_title or page.title
        description = _page_description(page)
        image = _page_image(page)
        if page._meta.model_name == "newspage":
            og_type = "article"
    description = _clean(description) or _clean(seo.tr("default_description"))

    image_url = _rendition_url(request, image, "fill-1200x630|format-jpeg") if image else ""
    if not image_url:
        image_url = _rendition_url(request, seo.share_image, "fill-1200x630|format-jpeg")

    canonical = request.build_absolute_uri(request.path)
    page_number = request.GET.get("page", "")
    if page_number.isdigit() and page_number != "1":
        canonical += f"?page={page_number}"

    links = alternates(context)
    x_default = next((url for lang, url in links if lang == "fa"), "")

    return {
        "request": request,
        "CSP_NONCE": context.get("CSP_NONCE", ""),
        "seo": seo,
        "noindex": not seo.allow_indexing,
        "title": title,
        "site_name": site_name,
        "description": description,
        "image_url": image_url,
        "og_type": og_type,
        "og_locale": "en_US" if english else "fa_IR",
        "canonical": canonical,
        "alternates": links,
        "x_default": x_default,
        "icon_32": _rendition_url(request, seo.site_icon, "fill-32x32|format-png"),
        "icon_180": _rendition_url(request, seo.site_icon, "fill-180x180|format-png"),
        "icon_192": _rendition_url(request, seo.site_icon, "fill-192x192|format-png"),
        "json_ld": _json_ld(context, request, page, subject, site, description, image_url, canonical),
    }


def _organization(request, site):
    from core.templatetags.site_tags import _localized_home

    home = _localized_home(request)
    org = {
        "@type": "Organization",
        "name": site.tr("site_name"),
        "url": _absolute(request, home.get_url(request)) if home else request.build_absolute_uri("/"),
    }
    alternate = site.site_name_en if not is_english() else site.site_name
    if alternate:
        org["alternateName"] = alternate
    logo = _rendition_url(request, site.logo, "max-512x512|format-png")
    if logo:
        org["logo"] = logo
    if site.email:
        org["email"] = site.email
    if site.phone:
        org["telephone"] = site.phone
    address = site.tr("address")
    if address:
        org["address"] = {"@type": "PostalAddress", "streetAddress": address, "addressCountry": "IR"}
    same_as = [u for u in (site.instagram_url, site.telegram_url, site.linkedin_url, site.aparat_url) if u]
    if same_as:
        org["sameAs"] = same_as
    return org


def _json_ld(context, request, page, subject, site, description, image_url, canonical):
    data = None
    if subject is not None and subject._meta.model_name == "product":
        from products.models import ShopSettings

        member = subject.member
        data = {
            "@type": "Product",
            "name": subject.tr("name"),
            "url": canonical,
            "brand": {"@type": "Organization", "name": member.tr("name")},
        }
        if description:
            data["description"] = description
        if image_url:
            data["image"] = image_url
        if subject.category_id:
            data["category"] = subject.category.tr("name")
        shop = ShopSettings.load(request_or_site=request)
        if subject.price and shop.prices_visible:
            data["offers"] = {
                "@type": "Offer",
                "price": str(subject.price),
                "priceCurrency": "IRR",
                "availability": "https://schema.org/" + ("InStock" if subject.in_stock else "OutOfStock"),
                "url": canonical,
            }
    elif subject is not None:
        data = {"@type": "Organization", "name": subject.tr("name"), "url": canonical}
        if description:
            data["description"] = description
        logo = _rendition_url(request, subject.logo, "max-512x512|format-png")
        if logo:
            data["logo"] = logo
        same_as = [u for u in (subject.instagram_url, subject.website_url) if u]
        if same_as:
            data["sameAs"] = same_as
        city = subject.tr("city")
        region = subject.region.tr("name") if subject.region_id else ""
        if city or region:
            data["address"] = {"@type": "PostalAddress", "addressCountry": "IR"}
            if city:
                data["address"]["addressLocality"] = city
            if region:
                data["address"]["addressRegion"] = region
        data["memberOf"] = {"@type": "Organization", "name": site.tr("site_name")}
    elif page is not None and page._meta.model_name == "homepage":
        org = _organization(request, site)
        data = {
            "@graph": [
                org,
                {"@type": "WebSite", "name": site.tr("site_name"), "url": org["url"],
                 "inLanguage": "en" if is_english() else "fa"},
            ]
        }
    elif page is not None and page._meta.model_name == "newspage":
        data = {
            "@type": "Event" if page.kind == "event" and page.event_start else "NewsArticle",
            "url": canonical,
        }
        if data["@type"] == "Event":
            data["name"] = page.title
            data["startDate"] = page.event_start.isoformat()
            if page.event_end:
                data["endDate"] = page.event_end.isoformat()
            if page.event_location:
                data["location"] = {"@type": "Place", "name": page.event_location, "address": page.event_location}
            data["organizer"] = {"@type": "Organization", "name": site.tr("site_name")}
        else:
            data["headline"] = page.title[:110]
            data["datePublished"] = page.date.isoformat()
            if page.last_published_at:
                data["dateModified"] = page.last_published_at.isoformat()
            data["publisher"] = _organization(request, site)
        if description:
            data["description"] = description
        if image_url:
            data["image"] = image_url
    if data is None:
        return ""
    data = {"@context": "https://schema.org", **data}
    text = json.dumps(data, ensure_ascii=False)
    # Keep the JSON from closing the <script> element early.
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return mark_safe(text)


@register.simple_tag(takes_context=True)
def seo_settings(context):
    return SeoSettings.load(request_or_site=context["request"])


@register.filter
def with_nonce(code, nonce):
    """Admin-entered HTML (analytics, trust badges) with the page's CSP nonce on its <script> tags."""
    from core.security import add_nonce

    return mark_safe(add_nonce(code or "", nonce))
