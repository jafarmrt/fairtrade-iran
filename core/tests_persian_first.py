"""
The admin and the member panel open in Persian, right to left, on a computer whose browser
asks for English (most computers in Iran). See core/locale.py.
"""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import translation

EN_BROWSER = {"HTTP_ACCEPT_LANGUAGE": "en-US,en;q=0.9"}


class PersianFirstTests(TestCase):
    def test_admin_sign_in_is_persian_for_an_english_browser(self):
        response = self.client.get("/admin/login/", **EN_BROWSER)
        self.assertContains(response, '<html lang="fa" dir="rtl"')
        self.assertContains(response, "ورود به پنل مدیریت")
        self.assertNotContains(response, "Admin sign-in")

    def test_admin_is_persian_until_the_user_picks_english(self):
        user = User.objects.create_superuser("editor", "editor@example.org", "pw-12345")
        self.client.force_login(user)
        response = self.client.get("/admin/", **EN_BROWSER)
        self.assertContains(response, '<html lang="fa" dir="rtl"')

        from wagtail.users.models import UserProfile

        profile = UserProfile.get_for_user(user)
        profile.preferred_language = "en"
        profile.save()
        response = self.client.get("/admin/")
        self.assertContains(response, '<html lang="en" dir="ltr"')

    def test_language_cookie_does_not_change_the_admin(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        self.assertContains(self.client.get("/admin/login/", **EN_BROWSER), '<html lang="fa" dir="rtl"')

    def test_missing_admin_page_is_not_sent_to_the_site(self):
        user = User.objects.create_superuser("editor", "editor@example.org", "pw-12345")
        self.client.force_login(user)
        response = self.client.get("/admin/no-such-page/", **EN_BROWSER)
        self.assertEqual(response.status_code, 404)

    def test_addresses_without_language_go_to_persian(self):
        self.assertRedirects(self.client.get("/panel/", **EN_BROWSER), "/fa/panel/", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/", **EN_BROWSER), "/fa/", fetch_redirect_response=False)

    def test_chosen_language_is_kept(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        self.assertRedirects(self.client.get("/", **EN_BROWSER), "/en/", fetch_redirect_response=False)

    def test_prefix_wins(self):
        response = self.client.get("/en/panel/login/")
        self.assertContains(response, 'lang="en"')
        response = self.client.get("/fa/panel/login/", **EN_BROWSER)
        self.assertContains(response, 'lang="fa"')


class PersianAdminDetailsTests(TestCase):
    def test_item_count_keeps_noun_singular(self):
        from wagtail.admin.paginator import WagtailPaginator

        from products.models import Category

        for i in range(3):
            Category.objects.create(name=f"دسته {i}", slug=f"c{i}")
        with translation.override("fa"):
            self.assertEqual(WagtailPaginator(Category.objects.all(), 20).items_count_label, "۳ دسته‌بندی محصول")
        with translation.override("en"):
            label = WagtailPaginator(Category.objects.all(), 20).items_count_label
            self.assertTrue(label.startswith("3 "))

    def test_payments_are_read_only(self):
        user = User.objects.create_superuser("editor", "editor@example.org", "pw-12345")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/admin/snippets/payments/payment/").status_code, 200)
        self.assertEqual(self.client.get("/admin/snippets/payments/payment/add/").status_code, 302)

    def test_money_column(self):
        from core.admin_columns import MoneyColumn

        class Row:
            price = 2_400_000

        with translation.override("fa"):
            self.assertEqual(MoneyColumn("price").get_value(Row()), "۲٬۴۰۰٬۰۰۰ ریال")

    def test_persian_digits_font_and_file_buttons_are_loaded(self):
        static = Path(settings.BASE_DIR) / "fairtrade" / "static"
        for css in ("admin.css", "fairtrade.css"):
            text = (static / "css" / css).read_text(encoding="utf-8")
            self.assertIn('"FtFaDigits"', text)
            self.assertIn(".ft-file__button", text)
        for weight in ("Regular", "Medium", "Bold"):
            self.assertTrue((static / "fonts" / f"Vazirmatn-FD-digits-{weight}.woff2").exists())
        user = User.objects.create_superuser("editor", "editor@example.org", "pw-12345")
        self.client.force_login(user)
        self.assertContains(self.client.get("/admin/"), "js/file-input.js")
        base = (Path(settings.BASE_DIR) / "fairtrade" / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("js/file-input.js", base)  # the site and the member panel
