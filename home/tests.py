from django.contrib.auth.models import AnonymousUser, Group
from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Collection, CollectionViewRestriction, Locale, Page

from core.models import MembershipSettings, SiteSettings
from home.models import HomePage
from pages.models import PrinciplesPage


class SeedContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=open("/dev/null", "w"))

    def test_seed_is_idempotent(self):
        before = Page.objects.count()
        call_command("seed_content", stdout=open("/dev/null", "w"))
        self.assertEqual(Page.objects.count(), before)

    def test_home_page_in_both_languages(self):
        fa = Locale.objects.get(language_code="fa")
        en = Locale.objects.get(language_code="en")
        home_fa = HomePage.objects.get(locale=fa)
        self.assertEqual(home_fa.get_translation(en).title, "Fair Trade House of Iran")

    def test_ten_principles_each_language(self):
        for page in PrinciplesPage.objects.all():
            self.assertEqual(page.principles.count(), 10)

    def test_settings_have_logo_and_defaults(self):
        site_settings = SiteSettings.load()
        self.assertIsNotNone(site_settings.logo)
        self.assertIsNotNone(site_settings.logo_light)
        membership = MembershipSettings.load()
        self.assertEqual(membership.secretariat_review_days, 7)
        self.assertEqual(membership.commission_review_days, 30)
        self.assertEqual(membership.trial_period_months, 3)

    def test_commission_collection_is_restricted_to_commission(self):
        collection = Collection.objects.get(name="اسناد کمیسیون نظارتی")
        restriction = CollectionViewRestriction.objects.get(collection=collection)
        self.assertEqual(list(restriction.groups.values_list("name", flat=True)), ["کمیسیون نظارتی"])
        self.assertTrue(Group.objects.filter(name="دبیرخانه").exists())


class PageRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=open("/dev/null", "w"))

    def test_root_redirects_to_persian(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/fa/", fetch_redirect_response=False)

    def test_pages_render(self):
        for url in ["/fa/", "/en/", "/fa/about/", "/en/about/", "/fa/principles/", "/en/principles/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_persian_is_rtl_and_english_is_ltr(self):
        self.assertContains(self.client.get("/fa/"), 'dir="rtl"')
        self.assertContains(self.client.get("/en/"), 'dir="ltr"')

    def test_language_switch_links_to_translation(self):
        self.assertContains(self.client.get("/fa/about/"), 'href="/en/about/"')
        self.assertContains(self.client.get("/en/principles/"), 'href="/fa/principles/"')

    def test_settings_edits_show_on_site(self):
        site_settings = SiteSettings.load()
        site_settings.phone = "021-12345678"
        site_settings.save()
        self.assertContains(self.client.get("/fa/"), "021-12345678")
