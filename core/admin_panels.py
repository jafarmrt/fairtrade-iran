"""
Live length counts for a page's search-engine fields in the page editor («سئو و منو» tab).

Google shows roughly the first 60 characters of a page's title and 160 of its
description, and cuts the rest. Under «عنوان سئو» the count covers the title as
the site really sends it: the SEO title (or the page title when it is empty)
followed by « | » and the site name, as fairtrade/templates/base.html builds it.
Under «توضیحات جست‌وجو» it says what is used when the field is left empty, in the
order core/templatetags/seo_tags.py uses: the page's summary (intro or hero_text),
then the site's default description (Settings > سئو).
The counting is done in the browser by static/js/admin-seo.js.
"""

import json

from django.core.exceptions import FieldDoesNotExist
from django.utils import translation
from wagtail.admin.panels import FieldPanel, MultiFieldPanel

# Typical display budget of search results, in characters (not settings: they are
# about search engines, not about the house).
TITLE_MAX = 60
DESCRIPTION_MIN = 70
DESCRIPTION_MAX = 160

# Fields used as the description when search_description is empty (seo_tags._page_description).
DESCRIPTION_FALLBACKS = ("intro", "hero_text")


def in_page_language(page, function):
    """Run function() in the page's own language (a new page has its parent's locale)."""
    locale = page.locale if getattr(page, "locale_id", None) else None
    with translation.override(locale.language_code if locale else translation.get_language()):
        return function()


def site_name_for(page):
    """The site name added to the page's <title>, in the page's own language."""
    from core.models import SiteSettings

    return in_page_language(page, lambda: SiteSettings.load().tr("site_name"))


def default_description_for(page):
    from core.models import SeoSettings

    return in_page_language(page, lambda: SeoSettings.load().tr("default_description"))


def description_fallbacks(page):
    """[[field name, label], …] of the page's own fields used when the description is empty."""
    fields = []
    for name in DESCRIPTION_FALLBACKS:
        try:
            field = page._meta.get_field(name)
        except FieldDoesNotExist:
            continue
        fields.append([name, str(field.verbose_name)])
    return fields


class SeoLengthPanel(FieldPanel):
    def __init__(self, field_name, *args, kind="title", **kwargs):
        self.kind = kind
        super().__init__(field_name, *args, **kwargs)

    def clone_kwargs(self):
        kwargs = super().clone_kwargs()
        kwargs["kind"] = self.kind
        return kwargs

    class BoundPanel(FieldPanel.BoundPanel):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            if self.bound_field is None or self.read_only:
                return
            attrs = {"data-ft-seo": self.panel.kind}
            if self.panel.kind == "title":
                attrs.update({"data-ft-seo-site": site_name_for(self.instance), "data-ft-seo-max": TITLE_MAX})
            else:
                attrs.update({
                    "data-ft-seo-min": DESCRIPTION_MIN,
                    "data-ft-seo-max": DESCRIPTION_MAX,
                    "data-ft-seo-fallback": json.dumps(description_fallbacks(self.instance), ensure_ascii=False),
                    "data-ft-seo-default": "1" if default_description_for(self.instance).strip() else "",
                })
            self.bound_field.field.widget.attrs.update(attrs)


def install():
    """
    Use the counting panels in every page type's «سئو و منو» tab. Our page models do not
    set promote_panels, so they all use Page.promote_panels; this is Wagtail's default
    list with the two search-engine fields swapped for SeoLengthPanel.
    """
    from django.utils.translation import gettext_lazy as _
    from wagtail.models import Page

    Page.promote_panels = [
        MultiFieldPanel(
            [
                FieldPanel("slug"),
                SeoLengthPanel("seo_title", kind="title"),
                SeoLengthPanel("search_description", kind="description"),
            ],
            _("For search engines"),
        ),
        MultiFieldPanel([FieldPanel("show_in_menus")], _("For site menus")),
    ]


def technical_note(text):
    """
    A short note at the top of a technical settings page («تنظیمات فنی (مسئول فنی)» in the
    settings menu, see core/wagtail_hooks.py): what the page is for, in one plain sentence.
    """
    from django.utils.html import format_html
    from wagtail.admin.panels import HelpPanel

    return HelpPanel(
        content=format_html(
            '<div class="help-block help-info"><svg class="icon icon-help icon" aria-hidden="true">'
            '<use href="#icon-help"></use></svg><p>{}</p></div>',
            text,
        )
    )
