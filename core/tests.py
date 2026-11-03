import json
import re

from django.core.management import call_command
from django.test import TestCase

from core.models import SeoSettings
from members.models import Member
from products.models import Product


def json_ld(response):
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', response.content.decode(), re.S)
    return json.loads(match.group(1)) if match else None


class SeoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=open("/dev/null", "w"))
        cls.armoz = Member.objects.get(slug="armoz")
        Product.objects.create(member=cls.armoz, name="خرما", name_en="Dates", summary="خرمای مضافتی",
                               slug="dates", price=1500000)
        Product.objects.create(member=cls.armoz, name="محصول فارسی", slug="fa-product")

    def test_home_has_meta_canonical_hreflang_and_organization(self):
        response = self.client.get("/fa/")
        self.assertContains(response, '<meta name="description"')
        self.assertContains(response, '<link rel="canonical" href="http://testserver/fa/">')
        self.assertContains(response, 'hreflang="en" href="http://testserver/en/"')
        self.assertContains(response, 'hreflang="x-default" href="http://testserver/fa/"')
        self.assertContains(response, '<meta property="og:title"')
        data = json_ld(response)
        types = [item["@type"] for item in data["@graph"]]
        self.assertEqual(types, ["Organization", "WebSite"])

    def test_product_page_has_product_data_and_both_languages(self):
        response = self.client.get("/fa/shop/dates/")
        self.assertContains(response, 'hreflang="en" href="http://testserver/en/shop/dates/"')
        self.assertContains(response, '<meta name="description" content="خرمای مضافتی">')
        self.assertContains(response, '<meta property="og:type" content="product">')
        data = json_ld(response)
        self.assertEqual(data["@type"], "Product")
        self.assertEqual(data["brand"]["name"], self.armoz.name)

    def test_untranslated_product_has_no_english_alternate(self):
        response = self.client.get("/fa/shop/fa-product/")
        self.assertNotContains(response, 'rel="alternate" hreflang="en"')

    def test_member_page_has_organization_data(self):
        data = json_ld(self.client.get("/fa/members/armoz/"))
        self.assertEqual(data["@type"], "Organization")

    def test_private_pages_are_noindex(self):
        self.assertContains(self.client.get("/fa/search/"), 'content="noindex"')
        self.assertNotContains(self.client.get("/fa/"), 'noindex')

    def test_robots_and_sitemap(self):
        robots = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /admin/", robots)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", robots)
        sitemap = self.client.get("/sitemap.xml").content.decode()
        for url in ["/fa/", "/en/", "/fa/shop/dates/", "/en/shop/dates/", "/fa/members/armoz/", "/en/members/armoz/"]:
            self.assertIn(f"http://testserver{url}</loc>", sitemap)
        self.assertNotIn("/en/shop/fa-product/", sitemap)

    def test_indexing_switch(self):
        seo = SeoSettings.load()
        seo.allow_indexing = False
        seo.footer_badges = '<a id="enamad-badge" href="#">e</a>'
        seo.save()
        self.assertIn("Disallow: /\n", self.client.get("/robots.txt").content.decode())
        response = self.client.get("/fa/")
        self.assertContains(response, '<meta name="robots" content="noindex, nofollow">')
        self.assertContains(response, 'id="enamad-badge"')


# ---- request limits and admin text placeholders ----

from django.contrib.auth import get_user_model  # noqa: E402
from django.core import mail  # noqa: E402
from django.core.cache import cache  # noqa: E402
from django.test import SimpleTestCase, override_settings  # noqa: E402

from contact.models import ContactPage  # noqa: E402
from core.templating import fill  # noqa: E402

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "throttle-tests"}}


@override_settings(CACHES=LOCMEM, THROTTLE_LIMITS={"login_user": (3, 900), "login_ip": (5, 900),
                                                    "password_reset": (2, 3600), "contact": (2, 3600)})
class ThrottleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=open("/dev/null", "w"))
        cls.user = get_user_model().objects.create_user("maryam", "maryam@example.org", "pw-12345")

    def setUp(self):
        cache.clear()

    def login(self, password, username="maryam", ip="10.0.0.1"):
        return self.client.post("/fa/panel/login/", {"username": username, "password": password}, REMOTE_ADDR=ip)

    def test_username_locked_after_failed_sign_ins_even_with_right_password(self):
        for _ in range(3):
            self.assertEqual(self.login("wrong").status_code, 200)
        response = self.login("pw-12345")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "۱۵ دقیقه")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_before_limit_resets_the_count(self):
        self.login("wrong")
        self.login("wrong")
        self.assertEqual(self.login("pw-12345").status_code, 302)
        self.client.logout()
        self.login("wrong")
        self.login("wrong")
        self.assertEqual(self.login("pw-12345").status_code, 302)

    def test_address_locked_after_many_usernames(self):
        for n in range(5):
            self.login("wrong", username=f"guess{n}")
        self.assertEqual(self.login("pw-12345").status_code, 200)
        self.assertEqual(self.login("pw-12345", ip="10.0.0.2").status_code, 302)

    def test_admin_sign_in_is_limited_too(self):
        for _ in range(3):
            self.client.post("/admin/login/", {"username": "maryam", "password": "wrong"}, REMOTE_ADDR="10.0.0.9")
        get_user_model().objects.filter(pk=self.user.pk).update(is_staff=True, is_superuser=True)
        self.client.post("/admin/login/", {"username": "maryam", "password": "pw-12345"}, REMOTE_ADDR="10.0.0.9")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_reset_emails_are_limited(self):
        for _ in range(4):
            response = self.client.post("/fa/panel/password/reset/", {"email": "maryam@example.org"})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 2)

    def test_contact_form_is_limited(self):
        page = ContactPage.objects.live().filter(locale__language_code="fa").first()
        for _ in range(2):
            self.assertNotEqual(self.client.post(page.url, {}).status_code, 429)
        self.assertEqual(self.client.post(page.url, {}).status_code, 429)


class FillTests(SimpleTestCase):
    def test_fills_known_names_and_keeps_the_rest(self):
        self.assertEqual(fill("سلام {name} {unknown}", {"name": "مریم"}), "سلام مریم {unknown}")

    def test_typos_and_attribute_access_do_not_break_or_leak(self):
        self.assertEqual(fill("{name.__class__} {0} {", {"name": "x"}), "{name.__class__} {0} {")
        self.assertEqual(fill("{a}", {"a": None}), "")
