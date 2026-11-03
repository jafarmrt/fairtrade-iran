from django import template
from django.utils.translation import get_language
from wagtail.models import Locale, Page

from core.iran import format_card, persian_digits
from core.models import is_english

register = template.Library()


@register.simple_tag
def tr(obj, field):
    """Return obj.<field>_en in English when it is filled, otherwise obj.<field>."""
    if obj is None:
        return ""
    if hasattr(obj, "tr"):
        return obj.tr(field)
    if is_english():
        value = getattr(obj, f"{field}_en", "")
        if value:
            return value
    return getattr(obj, field, "")


@register.filter
def money(value):
    """A rial amount with thousands separators: ۱۲٬۴۵۰٬۰۰۰ on Persian pages, 12,450,000 on English ones."""
    if value in (None, ""):
        return ""
    text = f"{int(value):,}"
    if is_english():
        return text
    return persian_digits(text).replace(",", "٬")


@register.filter
def card_format(value):
    """A 16-digit card number in groups of four (always Latin digits, shown left to right)."""
    return format_card(value or "")


@register.filter
def sheba_format(value):
    """IR12 3456 … in groups of four."""
    s = str(value or "")
    return " ".join(s[i:i + 4] for i in range(0, len(s), 4)) if s.startswith("IR") and len(s) == 26 else s


def _localized_home(request):
    site = getattr(request, "_wagtail_site", None)
    from wagtail.models import Site

    site = site or Site.find_for_request(request)
    if not site:
        return None
    root = site.root_page
    try:
        return root.get_translation(Locale.get_active()).specific
    except (Page.DoesNotExist, Locale.DoesNotExist):
        return root.specific


@register.simple_tag(takes_context=True)
def localized_home(context):
    return _localized_home(context["request"])


@register.simple_tag(takes_context=True)
def nav_pages(context):
    home = _localized_home(context["request"])
    if not home:
        return []
    return home.get_children().live().in_menu().specific()


@register.simple_tag(takes_context=True)
def page_of_type(context, model_path):
    """Find the first live page of a given type in the current language, e.g. 'membership.MembershipPage'."""
    from django.apps import apps

    model = apps.get_model(model_path)
    return model.objects.live().filter(locale=Locale.get_active()).first()


@register.simple_tag(takes_context=True)
def translation_url(context, lang_code):
    """URL of the current page in the other language, falling back to that language's home page."""
    request = context["request"]
    page = context.get("page")
    try:
        target_locale = Locale.objects.get(language_code=lang_code)
    except Locale.DoesNotExist:
        return f"/{lang_code}/"
    if page is not None and isinstance(page, Page):
        translation = page.get_translation_or_none(target_locale)
        if translation and translation.live:
            url = translation.get_url(request)
            sub = context.get("routable_suffix")
            return url + sub if sub else url
    match = getattr(request, "resolver_match", None)
    if page is None and match is not None and match.url_name != "wagtail_serve":
        # A plain Django view under i18n_patterns, such as the member panel or search.
        from django.urls import translate_url

        url = translate_url(request.get_full_path(), lang_code)
        if url != request.get_full_path():
            return url
    home = _localized_home(request)
    if home:
        translation = home.get_translation_or_none(target_locale)
        if translation:
            return translation.get_url(request)
    return f"/{lang_code}/"


@register.simple_tag
def current_lang():
    return (get_language() or "fa")[:2]
