import json
import re

from django.core.management import call_command
from django.test import TestCase

from core.models import SeoSettings
from members.models import Member
from products.models import Product


def json_ld(response):
    match = re.search(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', response.content.decode(), re.S)
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


# ---- Content-Security-Policy and two-step sign-in ----

from core.models import SecuritySettings  # noqa: E402
from core.security import add_nonce, origins_in  # noqa: E402


class CspTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=open("/dev/null", "w"))

    def test_public_pages_send_a_policy_with_the_nonce_on_our_scripts(self):
        response = self.client.get("/fa/")
        policy = response["Content-Security-Policy"]
        nonce = re.search(r"'nonce-([^']+)'", policy).group(1)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("https://payment.zarinpal.com", policy)
        scripts = re.findall(r"<script([^>]*)>", response.content.decode())
        self.assertTrue(scripts)
        for attrs in scripts:
            self.assertIn(f'nonce="{nonce}"', attrs)
        self.assertIn("camera=()", response["Permissions-Policy"])
        self.assertIn("geolocation=()", self.client.get("/admin/login/")["Permissions-Policy"])

    def test_admin_snippets_get_the_nonce_and_their_origins_are_allowed(self):
        seo = SeoSettings.load()
        seo.head_code = '<script defer src="https://stats.example.org/script.js" data-id="1"></script>'
        seo.footer_badges = "<a href='https://trustseal.enamad.ir/?id=1'><img src='https://trustseal.enamad.ir/logo.aspx'></a>"
        seo.save()
        response = self.client.get("/fa/")
        policy = response["Content-Security-Policy"]
        self.assertIn("https://stats.example.org", policy)
        self.assertIn("https://trustseal.enamad.ir", policy)
        nonce = re.search(r"'nonce-([^']+)'", policy).group(1)
        self.assertContains(response, f'<script nonce="{nonce}" defer src="https://stats.example.org/script.js"')

    def test_report_only_and_off_and_admin_untouched(self):
        security = SecuritySettings.load()
        security.csp_mode = "report"
        security.csp_extra_sources = "https://maps.example.org/embed\nnot a url"
        security.save()
        response = self.client.get("/fa/")
        self.assertNotIn("Content-Security-Policy", response)
        self.assertIn("https://maps.example.org", response["Content-Security-Policy-Report-Only"])
        security.csp_mode = "off"
        security.save()
        self.assertNotIn("Content-Security-Policy-Report-Only", self.client.get("/fa/"))
        self.assertNotIn("Content-Security-Policy", self.client.get("/admin/login/"))

    def test_helpers(self):
        self.assertEqual(add_nonce("<script>a</script><SCRIPT nonce='x'>", "N"),
                         '<script nonce="N">a</script><SCRIPT nonce=\'x\'>')
        self.assertEqual(origins_in('<img src="http://a.org/x"><script src="https://b.org:8443/y">'),
                         {"https://b.org:8443"})


@override_settings(CACHES=LOCMEM)
class TwoFactorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=open("/dev/null", "w"))
        User = get_user_model()
        cls.admin = User.objects.create_superuser("boss", "boss@example.org", "pw-12345")
        cls.member = User.objects.create_user("maryam", "maryam@example.org", "pw-12345")

    def setUp(self):
        cache.clear()
        security = SecuritySettings.load()
        security.two_factor = "staff"
        security.save()

    def sign_in(self):
        self.client.post("/admin/login/", {"username": "boss", "password": "pw-12345"})

    def code_from_mail(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def test_admin_needs_the_emailed_code(self):
        self.sign_in()
        response = self.client.get("/admin/")
        self.assertRedirects(response, "/two-factor/?next=/admin/", fetch_redirect_response=False)
        self.client.get("/two-factor/?next=/admin/")
        self.assertEqual(mail.outbox[-1].to, ["boss@example.org"])
        response = self.client.post("/two-factor/", {"code": "000000" if self.code_from_mail() != "000000" else "111111",
                                                     "next": "/admin/"})
        self.assertContains(response, "کد درست نیست")
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        persian = self.code_from_mail().translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        response = self.client.post("/two-factor/", {"code": persian, "next": "/admin/"})
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_remembered_browser_skips_the_code_next_time(self):
        self.sign_in()
        self.client.get("/two-factor/")
        self.client.post("/two-factor/", {"code": self.code_from_mail(), "remember": "1"})
        self.client.post("/admin/logout/")
        sent = len(mail.outbox)
        self.sign_in()
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertEqual(len(mail.outbox), sent)

    def test_too_many_wrong_codes_need_a_new_code(self):
        self.sign_in()
        self.client.get("/two-factor/")
        code = self.code_from_mail()
        for _ in range(5):
            self.client.post("/two-factor/", {"code": "12345" + ("0" if code[-1] != "0" else "1")})
        response = self.client.post("/two-factor/", {"code": code})
        self.assertContains(response, "منقضی")

    def test_members_without_admin_access_and_switch_off(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get("/fa/").status_code, 200)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/fa/").status_code, 302)
        with self.settings(TWO_FACTOR_DISABLED=True):
            self.assertEqual(self.client.get("/fa/").status_code, 200)
        security = SecuritySettings.load()
        security.two_factor = "off"
        security.save()
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_next_must_stay_on_this_site(self):
        self.sign_in()
        self.client.get("/two-factor/")
        response = self.client.post("/two-factor/", {"code": self.code_from_mail(), "next": "https://evil.example/"})
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)
