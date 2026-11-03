"""The admin in Persian and arranged for volunteers: dates, translations, sign-in page, menus, dashboard, guide."""

import datetime
import gettext
import io
import json
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.utils import formats, translation
from wagtail.models import Page

from core import jalali_dates, pofile
from home.management.commands import seed_data as data


class JalaliDateFormatTests(SimpleTestCase):
    day = datetime.date(2026, 11, 3)
    moment = datetime.datetime(2026, 11, 3, 22, 35)

    def test_persian_display_formats_are_jalali(self):
        with translation.override("fa"):
            self.assertEqual(formats.date_format(self.day), "۱۲ آبان ۱۴۰۵")
            self.assertEqual(formats.date_format(self.moment, "DATETIME_FORMAT"), "۱۲ آبان ۱۴۰۵، ساعت ۲۲:۳۵")
            self.assertEqual(formats.date_format(self.day, "SHORT_DATE_FORMAT"), "۱۴۰۵/۰۸/۱۲")
            self.assertEqual(formats.date_format(self.moment, "SHORT_DATETIME_FORMAT"), "۱۴۰۵/۰۸/۱۲، ۲۲:۳۵")
            # Wagtail passes the resolved format string instead of its name.
            resolved = formats.get_format("DATETIME_FORMAT")
            self.assertEqual(formats.date_format(self.moment, resolved), "۱۲ آبان ۱۴۰۵، ساعت ۲۲:۳۵")
            rendered = Template('{{ d|date:"SHORT_DATE_FORMAT" }}').render(Context({"d": self.day}))
            self.assertEqual(rendered, "۱۴۰۵/۰۸/۱۲")

    def test_explicit_formats_and_english_are_unchanged(self):
        with translation.override("fa"):
            self.assertEqual(formats.date_format(self.day, "Y-m-d"), "2026-11-03")
            self.assertEqual(formats.date_format(self.moment, "c"), "2026-11-03T22:35:00")
        with translation.override("en"):
            self.assertIn("2026", formats.date_format(self.day))

    def test_copies_imported_by_wagtail_are_replaced(self):
        from wagtail.admin import active_filters

        self.assertIs(formats.date_format, jalali_dates.date_format)
        self.assertIs(active_filters.date_format, jalali_dates.date_format)


class TranslationCatalogTests(SimpleTestCase):
    """locale/fa completes Wagtail's Persian translations; the .mo files must be rebuilt from the .po files."""

    folder = Path(settings.BASE_DIR) / "locale" / "fa" / "LC_MESSAGES"
    NAMED = re.compile(r"%\((\w+)\)[sdif]")
    POSITIONAL = re.compile(r"%[sdif]")
    BRACES = re.compile(r"\{(\w*)\}")

    def catalogs(self):
        files = sorted(self.folder.glob("*.po"))
        self.assertTrue(files)
        for po in files:
            yield po, pofile.parse(po.read_text(encoding="utf-8"))

    def test_mo_files_are_up_to_date(self):
        for po, entries in self.catalogs():
            with self.subTest(po.name):
                self.assertEqual(
                    pofile.mo_bytes(entries), po.with_suffix(".mo").read_bytes(),
                    f"{po.name} changed: run `python manage.py build_translations`",
                )
                gettext.GNUTranslations(io.BytesIO(po.with_suffix(".mo").read_bytes()))  # loads cleanly

    def test_placeholders_match(self):
        for po, entries in self.catalogs():
            for e in entries:
                if not e["id"]:
                    continue  # header
                source = e["id"] + (e.get("plural") or "")
                for text in e["str"] if isinstance(e["str"], list) else [e["str"]]:
                    if not text:
                        continue
                    with self.subTest(po=po.name, msgid=e["id"][:60]):
                        # A placeholder the original does not have would crash the page.
                        self.assertLessEqual(set(self.NAMED.findall(text)), set(self.NAMED.findall(source)))
                        self.assertLessEqual(set(self.BRACES.findall(text)), set(self.BRACES.findall(source)))
                        self.assertEqual(len(self.POSITIONAL.findall(text)), len(self.POSITIONAL.findall(e["id"])))

    def test_project_translations_win(self):
        with translation.override("fa"):
            self.assertEqual(translation.gettext("Password"), "رمز عبور")
            self.assertEqual(translation.gettext("Dashboard"), "پیشخوان")
            self.assertEqual(translation.gettext("Snippets"), "قطعه‌ها")


class AdminLoginPageTests(TestCase):
    def test_house_branding_and_persian_labels(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ورود به پنل مدیریت")
        self.assertContains(response, "خانه تجارت عادلانه ایران")
        self.assertContains(response, "رمز عبور")
        self.assertNotContains(response, ">Password<")
        self.assertContains(response, "css/admin.css")
        self.assertContains(response, "/fa/panel/login/")  # members are pointed to their own panel

    def test_no_django_admin(self):
        self.assertEqual(self.client.get("/django-admin/", follow=True).status_code, 404)


def sidebar(response):
    """The admin's main menu as [(name, label, url, [children])], from the sidebar's JSON."""
    match = re.search(r'<script id="wagtail-sidebar-props" type="application/json">(.*?)</script>',
                      response.content.decode(), re.S)
    props = json.loads(match.group(1))

    def walk(items):
        result = []
        for item in items:
            args = item.get("_args") or []
            info = args[0]
            children = walk(args[1]) if len(args) > 1 and isinstance(args[1], list) else []
            result.append((info.get("name"), info.get("label"), info.get("url"), children))
        return result

    for module in props["modules"]:
        if module["_type"] == "wagtail.sidebar.MainMenuModule":
            return walk(module["_args"][0])
    return []


class AdminForVolunteersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=io.StringIO())
        cls.admin = User.objects.create_superuser("root", "root@example.org", "pw")
        cls.pr = cls.user("pr", data.PR)
        cls.secretariat = cls.user("sec", data.SECRETARIAT)

    @classmethod
    def user(cls, name, group):
        user = User.objects.create_user(name, f"{name}@example.org", "pw")
        user.groups.add(Group.objects.get(name=group))
        return user

    def menu_for(self, user):
        self.client.force_login(user)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        return response, sidebar(response)

    def test_main_menu_order_and_groups(self):
        _, menu = self.menu_for(self.admin)
        names = [name for name, *_ in menu]
        expected = ["explorer", "images", "documents", "forms", "membership", "directory", "shop",
                    "complaints", "appeals", "assembly", "sms", "snippets", "reports", "settings", "help"]
        self.assertEqual([n for n in names if n in expected], expected)
        groups = {name: [url for _, _, url, _ in children] for name, _, _, children in menu if children}
        self.assertIn("/admin/standing/", groups["membership"])  # was missing from the menu
        self.assertIn("/admin/shop_orders/", groups["shop"])  # was missing from the menu
        self.assertIn("/admin/wholesale_inquiries/", groups["shop"])
        self.assertIn("/admin/snippets/products/product/", groups["shop"])
        self.assertNotIn("/admin/snippets/products/product/", groups["directory"])
        settings_items = dict((m[0], m[3]) for m in menu)["settings"]
        self.assertEqual(settings_items[0][1], "تنظیمات سایت")  # the house's settings before Wagtail's

    def test_volunteers_do_not_see_technical_items(self):
        _, menu = self.menu_for(self.pr)
        names = [name for name, *_ in menu]
        self.assertNotIn("snippets", names)
        self.assertIn("explorer", names)
        reports = dict((m[0], m[3]) for m in menu).get("reports", [])
        self.assertNotIn("page-types-usage", [c[0] for c in reports])
        help_items = dict((m[0], m[3]) for m in menu)["help"]
        self.assertEqual(help_items[0][2], "/admin/guide/")
        self.assertFalse([c for c in help_items if c[0] in ("editor-guide",) or c[0].startswith("whats-new")])

    def test_dashboard_shortcuts_follow_permissions(self):
        response, _ = self.menu_for(self.pr)
        self.assertContains(response, "کارهای پرکاربرد")
        self.assertContains(response, "نوشتن خبر یا رویداد")
        self.assertContains(response, "بارگذاری عکس")
        self.assertNotContains(response, "سفارش‌های فروشگاه")
        response, _ = self.menu_for(self.secretariat)
        self.assertContains(response, "پرونده‌های عضویت")
        self.assertNotContains(response, "نوشتن خبر یا رویداد")

    def test_guide(self):
        self.client.force_login(self.pr)
        response = self.client.get("/admin/guide/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="pages"')
        self.assertContains(response, data.EDITORIAL_WORKFLOW)
        self.assertContains(response, "اسناد هیئت مدیره")  # collections and who may open them
        self.assertNotContains(response, 'id="membership"')
        self.client.force_login(self.secretariat)
        response = self.client.get("/admin/guide/")
        self.assertContains(response, 'id="membership"')
        self.assertNotContains(response, 'id="pages"')

    def test_root_page_title(self):
        self.assertEqual(Page.get_first_root_node().title, data.ROOT_TITLE)
