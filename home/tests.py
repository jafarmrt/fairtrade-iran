import os
from unittest import mock

from django.contrib.auth.models import AnonymousUser, Group
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
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

    def test_editors_cannot_reach_confidential_documents(self):
        """Edit rights on a document allow moving it to the public collection, so they follow view rights."""
        from django.contrib.auth import get_user_model
        from django.core.files.base import ContentFile
        from django.test import Client
        from wagtail.models import GroupCollectionPermission

        from archive.models import ArchiveDocument

        root = Collection.get_first_root_node()
        for name in ("روابط عمومی", "هیئت مدیره"):
            self.assertFalse(GroupCollectionPermission.objects.filter(
                group__name=name, collection=root, permission__content_type__app_label="wagtaildocs").exists())
        commission = Collection.objects.get(name="اسناد کمیسیون نظارتی")
        public = Collection.objects.get(name="اسناد عمومی")
        secret = ArchiveDocument(title="گزارش محرمانه", collection=commission)
        secret.file.save("secret.txt", ContentFile(b"confidential"), save=True)
        user = get_user_model().objects.create_user("pr-volunteer", "pr@example.org", "x-pass-12345")
        user.groups.add(Group.objects.get(name="روابط عمومی"))
        client = Client()
        client.force_login(user)
        self.assertNotContains(client.get("/admin/documents/"), "گزارش محرمانه")
        client.post(f"/admin/documents/edit/{secret.pk}/", {"title": secret.title, "collection": public.pk})
        secret.refresh_from_db()
        self.assertEqual(secret.collection, commission)
        # They still manage public documents, and the commission manages its own.
        self.assertTrue(GroupCollectionPermission.objects.filter(
            group__name="کمیسیون نظارتی", collection=commission, permission__codename="change_document").exists())
        self.assertTrue(GroupCollectionPermission.objects.filter(
            group__name="روابط عمومی", collection=public, permission__codename="add_document").exists())


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


DEMO_MEDIA = __import__("tempfile").mkdtemp(prefix="ft-demo-media-")


@override_settings(MEDIA_ROOT=DEMO_MEDIA)
class SeedDemoTests(TestCase):
    """seed_demo fills a test copy (deploy/local/run-demo.sh) and refuses on a real site."""

    def run_demo(self, *args, password="demo-pass-123"):
        with mock.patch.dict(os.environ, {"DEMO_PASSWORD": password}):
            call_command("seed_demo", *args, stdout=open("/dev/null", "w"))

    def test_refuses_without_demo_mode(self):
        with self.assertRaises(CommandError):
            self.run_demo()

    @override_settings(DEMO_MODE=True)
    def test_refuses_short_password(self):
        with self.assertRaises(CommandError):
            self.run_demo(password="short")

    @override_settings(DEMO_MODE=True)
    def test_demo_content_logins_and_banner(self):
        from django.contrib.auth import get_user_model

        from core.models import SeoSettings
        from payments.models import PaymentSettings
        from products.models import Product

        self.run_demo()
        products = Product.objects.count()
        self.assertGreaterEqual(products, 5)
        self.assertFalse(SeoSettings.load().allow_indexing)
        self.assertEqual(PaymentSettings.load().provider, PaymentSettings.Provider.TEST)

        User = get_user_model()
        self.assertTrue(User.objects.get(username="demo-admin").check_password("demo-pass-123"))
        member_user = User.objects.get(username="demo-member")
        self.assertFalse(member_user.is_staff)
        self.assertTrue(member_user.managed_members.exists())

        # Idempotent, and --passwords-only only resets passwords.
        self.run_demo()
        self.run_demo("--passwords-only", password="another-pass-456")
        self.assertEqual(Product.objects.count(), products)
        self.assertTrue(User.objects.get(username="demo-admin").check_password("another-pass-456"))

        html = self.client.get("/fa/").content.decode()
        self.assertIn("demo-banner", html)
        self.assertIn('content="noindex, nofollow"', html)

    def test_no_banner_on_real_site(self):
        call_command("seed_content", stdout=open("/dev/null", "w"))
        self.assertNotIn("demo-banner", self.client.get("/fa/").content.decode())
