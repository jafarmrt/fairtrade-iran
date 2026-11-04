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

        # «نمایش در سایت: بله» above a filtered list, not «نمایش در سایت: True».
        _boolean_filter_labels()

        # Settings > تنظیمات فنی > سایت‌ها: Wagtail labels three of its columns from the field
        # name ("Port", "Site name", "Root page"), which no translation reaches.
        _sites_column_labels()

        # «بیشترین حجم پرونده: ۱۰ مگابایت», not «10.0 MB» (the units are in locale/fa).
        _persian_file_sizes()


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


def _boolean_filter_labels():
    import django_filters
    from wagtail.admin.active_filters import ActiveFilter, BaseFilterAdapter, register_filter_adapter_class

    class BooleanFilterAdapter(BaseFilterAdapter):
        def get_active_filters(self):
            # The widget's own choices: «بله / خیر» (Wagtail's translation) or «دارد / ندارد».
            choices = {key: label for key, label in getattr(self.filter.field.widget, "choices", [])}
            key = "true" if self.value else "false"
            yield ActiveFilter(
                self.bound_field.auto_id,
                self.filter.label,
                str(choices.get(key, self.value)),
                self.get_url_without_filter_param(self.name),
            )

    register_filter_adapter_class(django_filters.BooleanFilter, BooleanFilterAdapter)


def _sites_column_labels():
    from django.utils.text import capfirst
    from django.utils.translation import gettext_lazy
    from wagtail.sites.views import IndexView

    labels = {"port": "port", "site_name": "site name", "root_page": "root page"}  # Wagtail's own msgids
    for column in IndexView.columns:
        if column.name in labels:
            column.label = capfirst(gettext_lazy(labels[column.name]))


def _persian_file_sizes():
    import re

    import wagtail.images.fields as image_fields
    from django.template import defaultfilters
    from django.utils.translation import get_language

    django_filesizeformat = defaultfilters.filesizeformat

    def filesizeformat(bytes_):
        value = django_filesizeformat(bytes_)
        if (get_language() or "").startswith("fa"):
            value = re.sub(r"(\d)\.0(?=\D)", r"\1", value)  # "10.0 MB" -> "10 MB"
        return value

    # The filter in templates, and the name Wagtail's image field imported.
    defaultfilters.filesizeformat = filesizeformat
    defaultfilters.register.filter("filesizeformat", filesizeformat, is_safe=True)
    image_fields.filesizeformat = filesizeformat
