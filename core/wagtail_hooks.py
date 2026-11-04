"""
The Wagtail admin arranged for the house's volunteers, most of whom are not technical:

- the house's look (font, colours, logo) on every admin page and the sign-in page: static/css/admin.css,
  with the templates in core/templates/wagtailadmin/;
- one fixed order for the main menu and the settings menu, the daily work first;
- technical items (the raw «قطعه‌ها» list, Wagtail's English release notes and editor guide,
  the page-types report) hidden from everyone but superusers;
- shortcuts on the dashboard and a Persian guide («راهنمای پنل») in the help menu.
"""

from django.templatetags.static import static
from django.urls import path, reverse
from django.utils.html import format_html
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.components import Component

from . import admin_views


@hooks.register("insert_global_admin_css")
def house_admin_css():
    return format_html('<link rel="stylesheet" href="{}">', static("css/admin.css"))


@hooks.register("insert_editor_js")
def seo_length_js():
    """Counts under «عنوان سئو» and «توضیحات جست‌وجو» while they are typed (core/admin_panels.py)."""
    return format_html('<script src="{}" defer></script>', static("js/admin-seo.js"))


# ---- main menu ----

# Top to bottom (Wagtail shows menu items by their `order`). Content first, for the PR
# working group, then the house's own work. Each person sees only what their group has
# permission for. A menu item that is not listed here (a new app's) keeps its own order,
# which by default puts it after «پیامک» and before «قطعه‌ها».
MAIN_MENU_ORDER = {
    "explorer": 100,     # صفحه‌ها
    "images": 200,       # عکس‌ها
    "documents": 300,    # اسناد
    "forms": 400,        # پیام‌های فرم‌ها (the contact form)
    "membership": 500,   # عضویت (membership/wagtail_hooks.py)
    "directory": 600,    # اعضا (members/wagtail_hooks.py)
    "shop": 700,         # فروشگاه (shop/wagtail_hooks.py)
    "complaints": 800,   # شکایات
    "appeals": 900,      # اعتراض‌ها
    "assembly": 1000,    # مجمع عمومی
    "sms": 1100,         # پیامک
    "snippets": 9000,    # قطعه‌ها: superusers only; everything in it is also in the groups above
    "reports": 9100,     # گزارش‌ها
    "settings": 10000,   # تنظیمات
    "help": 11000,       # راهنما
}
FORMS_LABEL = "پیام‌های فرم‌ها"


@hooks.register("construct_main_menu")
def arrange_main_menu(request, menu_items):
    if not request.user.is_superuser:
        menu_items[:] = [item for item in menu_items if item.name != "snippets"]
    for item in menu_items:
        item.order = MAIN_MENU_ORDER.get(item.name, item.order)
        if item.name == "forms":
            item.label = FORMS_LABEL  # Wagtail's «فرم‌ها» looked like the membership form questions


# ---- settings menu ----

# The house's own settings first (what a volunteer may need to change), then accounts,
# then Wagtail's technical settings. A settings model not listed here keeps Wagtail's
# default order (1000): after the house's settings, before «کاربران».
SETTINGS_MENU_ORDER = {
    "core.sitesettings": 10,          # تنظیمات سایت: logo, name, contact
    "core.membershipsettings": 20,    # fees, deadlines, bank details
    "products.shopsettings": 30,
    "payments.paymentsettings": 40,
    "wholesale.wholesalesettings": 50,
    "members.directorysettings": 60,
    "memberpanel.panelsettings": 70,
    "appeals.appealsettings": 80,
    "assembly.assemblysettings": 90,
    "sms.smssettings": 100,
    "core.seosettings": 110,
    "core.pwasettings": 120,
    "core.securitysettings": 130,
    "users": 5000,
    "groups": 5010,
    "collections": 5020,
    "redirects": 5030,
    "workflows": 5040,
    "workflow-tasks": 5050,
    "sites": 5060,
    "locales": 5070,
}


def _settings_name(item):
    model = getattr(item, "model", None)  # wagtail.contrib.settings' menu items carry their model
    return model._meta.label_lower if model is not None else item.name


@hooks.register("construct_settings_menu")
def arrange_settings_menu(request, menu_items):
    for item in menu_items:
        item.order = SETTINGS_MENU_ORDER.get(_settings_name(item), item.order)


# ---- reports and help ----

TECHNICAL_REPORTS = {"page-types-usage"}


@hooks.register("construct_reports_menu")
def simplify_reports_menu(request, menu_items):
    if not request.user.is_superuser:
        menu_items[:] = [item for item in menu_items if item.name not in TECHNICAL_REPORTS]


@hooks.register("register_help_menu_item")
def guide_menu_item():
    return MenuItem("راهنمای پنل", reverse("ft_admin_guide"), name="ft-guide", icon_name="help", order=10)


@hooks.register("construct_help_menu")
def simplify_help_menu(request, menu_items):
    kept = []
    for item in menu_items:
        if item.name.startswith("whats-new-in-wagtail"):
            continue  # English release notes for developers
        if item.name == "editor-guide":
            if not request.user.is_superuser:
                continue
            item.label = "راهنمای کامل Wagtail (انگلیسی)"
        kept.append(item)
    menu_items[:] = kept


@hooks.register("register_admin_urls")
def guide_url():
    return [path("guide/", admin_views.guide, name="ft_admin_guide")]


# ---- dashboard ----


class ShortcutsPanel(Component):
    """«کارهای پرکاربرد»: tiles for the things each person does most, at the top of the dashboard."""

    name = "ft_shortcuts"
    order = 10
    template_name = "core/admin/shortcuts_panel.html"

    def __init__(self, request):
        self.request = request

    def get_context_data(self, parent_context=None):
        return {"shortcuts": admin_views.shortcuts_for(self.request.user)}


@hooks.register("construct_homepage_panels")
def add_shortcuts_panel(request, panels):
    panels.append(ShortcutsPanel(request))
