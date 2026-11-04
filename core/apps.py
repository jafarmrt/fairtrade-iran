from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "هسته"

    def ready(self):
        from django.db import models
        from wagtail.admin.forms.models import register_form_field_override

        from . import admin_panels, jalali_dates
        from . import throttle  # noqa: F401  (connects the sign-in signals)
        from .widgets import JalaliDateInput, JalaliDateTimeInput

        # Dates shown on Persian pages and in the admin (listings, history, "locked at") are Jalali.
        jalali_dates.install()

        # Every date and date-time in the Wagtail admin (snippets, settings, page "go live" schedule) is Jalali.
        register_form_field_override(models.DateField, override={"widget": JalaliDateInput})
        register_form_field_override(models.DateTimeField, override={"widget": JalaliDateTimeInput})

        # Length counts under the SEO title and search description in every page's «سئو و منو» tab.
        admin_panels.install()

        # "۹ محصول", not "9 محصولات", under every admin list: Persian keeps the noun singular after a number.
        _persian_item_counts()


def _persian_item_counts():
    from django.utils.functional import cached_property
    from django.utils.translation import get_language, gettext
    from wagtail.admin.paginator import WagtailPaginator

    english = WagtailPaginator.items_count_label.func

    def items_count_label(self):
        if (get_language() or "").startswith("fa"):
            from .jalali import to_persian_digits

            # gettext: a few of Wagtail's models (Locale) have an untranslated default name.
            return f"{to_persian_digits(self.count)} {gettext(str(self.verbose_name))}"
        return english(self)

    WagtailPaginator.items_count_label = cached_property(items_count_label)
    WagtailPaginator.items_count_label.__set_name__(WagtailPaginator, "items_count_label")
