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
