"""
The admin and the member panel made simpler for volunteers (second round of the Persian
usability review): waiting work first on the dashboard, a short member-panel menu, a
translation column instead of English names, technical settings in their own fold.
"""

import io

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.utils import translation

from home.management.commands import seed_data as data
from members.models import Member
from products.models import Product

from .tests_admin_ui import sidebar


class UsabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=io.StringIO())
        cls.admin = User.objects.create_superuser("root", "root@example.org", "pw")
        cls.pr = User.objects.create_user("pr", "pr@example.org", "pw")
        cls.pr.groups.add(Group.objects.get(name=data.PR))
        cls.armoz = Member.objects.get(slug="armoz")

    def dashboard(self, user):
        self.client.force_login(user)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        return response

    def test_waiting_work_comes_first_with_a_count_and_a_link(self):
        Product.objects.create(member=self.armoz, name="حوله", slug="towel-x", needs_review=True)
        Product.objects.create(member=self.armoz, name="سبد", slug="basket-x", needs_review=True)
        html = self.dashboard(self.admin).content.decode()
        self.assertIn("کارهای منتظر شما", html)
        self.assertLess(html.index("کارهای منتظر شما"), html.index("کارهای پرکاربرد"))
        self.assertIn("محصول تازهٔ اعضا منتظر بررسی", html)
        self.assertIn("/admin/snippets/products/product/?needs_review=true", html)
        self.assertIn('ft-pending__count">۲<', html.replace("\n", "").replace(" <", "<"))

    def test_nothing_waiting(self):
        self.assertContains(self.dashboard(self.pr), "کاری منتظر شما نیست.")

    def test_dashboard_has_few_tiles(self):
        html = self.dashboard(self.admin).content.decode()
        self.assertLessEqual(html.count('class="ft-shortcuts__tile'), 8)
        self.assertIn("راهنمای پنل", html)

    def test_translation_column_and_filter(self):
        Member.objects.filter(pk=self.armoz.pk).update(name_en="")
        self.client.force_login(self.admin)
        response = self.client.get("/admin/snippets/members/member/")
        self.assertContains(response, "ترجمهٔ انگلیسی")
        self.assertNotContains(response, "Armoz")  # no column of English names
        response = self.client.get("/admin/snippets/members/member/?english=false")
        self.assertEqual(list(response.context["object_list"]), [Member.objects.get(pk=self.armoz.pk)])
        self.assertContains(response, "ندارد")  # the active-filter chip, not "False"
        response = self.client.get("/admin/snippets/members/member/?english=true")
        self.assertNotIn(self.armoz.pk, [m.pk for m in response.context["object_list"]])

    def test_technical_settings_are_folded_away(self):
        settings_items = dict((m[0], m[3]) for m in sidebar(self.dashboard(self.admin)))["settings"]
        names = [item[0] for item in settings_items]
        self.assertEqual(names[-1], "technical")
        technical = settings_items[-1][3]
        urls = [item[2] for item in technical]
        self.assertIn("/admin/settings/payments/paymentsettings/", urls)
        self.assertIn("/admin/settings/core/securitysettings/", urls)
        self.assertIn("/admin/sites/", urls)
        self.assertNotIn("/admin/settings/core/sitesettings/", urls)
        response = self.client.get("/admin/settings/sms/smssettings/", follow=True)
        self.assertContains(response, "سامانهٔ پیامک برای کد ورود اعضا")

    def test_sites_columns_are_persian(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/sites/")
        for english in ("Site name", "Root page", ">Port<"):
            self.assertNotContains(response, english)
        self.assertContains(response, "نام سایت")

    def test_upload_limit_in_persian_units(self):
        from django.template.defaultfilters import filesizeformat

        with translation.override("fa"):
            self.assertEqual(filesizeformat(10 * 1024 * 1024), "10\xa0مگابایت")
            self.assertEqual(filesizeformat(1536 * 1024), "1.5\xa0مگابایت")
        with translation.override("en"):
            self.assertEqual(filesizeformat(10 * 1024 * 1024), "10.0\xa0MB")


class MemberPanelMenuTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=io.StringIO())
        cls.member = Member.objects.get(slug="armoz")
        cls.user = User.objects.create_user("maryam", "maryam@example.org", "pw-12345")
        cls.member.managers.add(cls.user)

    def test_main_sections_and_folds(self):
        self.client.force_login(self.user)
        response = self.client.get(f"/fa/panel/{self.member.pk}/profile/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        start = html.index('class="filter-tabs panel-nav"')
        nav = html[start:html.index("</nav>", start)]
        self.assertIn("بیشتر", nav)
        self.assertIn("حساب من", nav)
        self.assertIn("شمارهٔ موبایل برای ورود", nav)
        self.assertIn("خروج از پنل", nav)
        # «بیشتر» and «حساب من» come after the main sections.
        self.assertLess(nav.index("پروفایل"), nav.index("بیشتر"))
        self.assertLess(nav.index("بیشتر"), nav.index("حساب من"))
