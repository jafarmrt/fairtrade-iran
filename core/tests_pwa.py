"""The installable phone version (PWA): manifest, service worker, offline page and which pages may be kept."""

import io
import json

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models import PwaSettings
from core.pwa import CACHE_HINT_HEADER

QUIET = io.StringIO()


class PwaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=QUIET)

    def manifest(self, lang):
        response = self.client.get(f"/{lang}/manifest.webmanifest")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/manifest+json"))
        return json.loads(response.content)

    def test_manifest_in_both_languages(self):
        fa = self.manifest("fa")
        self.assertEqual(fa["lang"], "fa")
        self.assertEqual(fa["dir"], "rtl")
        self.assertEqual(fa["start_url"], "/fa/")
        self.assertEqual(fa["scope"], "/")
        self.assertEqual(fa["name"], "خانه تجارت عادلانه ایران")
        self.assertEqual(fa["display"], "standalone")
        en = self.manifest("en")
        self.assertEqual(en["dir"], "ltr")
        self.assertEqual(en["name"], "Fair Trade House of Iran")
        self.assertEqual(en["short_name"], "Fair Trade Iran")
        purposes = {(i["sizes"], i["purpose"]) for i in en["icons"]}
        self.assertIn(("192x192", "any"), purposes)
        self.assertIn(("512x512", "any"), purposes)
        self.assertIn(("512x512", "maskable"), purposes)

    def test_manifest_follows_admin_settings(self):
        pwa = PwaSettings.load()
        pwa.app_name_en = "FT House"
        pwa.theme_color = "#873319"
        pwa.save()
        data = self.manifest("en")
        self.assertEqual(data["name"], "FT House")
        self.assertEqual(data["theme_color"], "#873319")
        # Persian falls back to the site name when its own field is empty.
        self.assertEqual(self.manifest("fa")["name"], "خانه تجارت عادلانه ایران")

    def test_head_links_manifest_and_install_banner(self):
        response = self.client.get("/fa/")
        self.assertContains(response, '<link rel="manifest" href="/fa/manifest.webmanifest">')
        self.assertContains(response, 'name="theme-color" content="#1a1c46"')
        self.assertContains(response, 'register("/sw.js"')
        self.assertContains(response, 'class="install-banner"')
        self.assertContains(self.client.get("/en/"), 'href="/en/manifest.webmanifest"')

    def test_service_worker(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/javascript"))
        self.assertIn("no-cache", response["Cache-Control"])
        body = response.content.decode()
        config = json.loads(body.split("const CONFIG = ", 1)[1].split(";\n", 1)[0])
        self.assertEqual(config["offline"], {"fa": "/fa/offline/", "en": "/en/offline/"})
        for prefix in ("/admin/", "/fa/panel/", "/en/panel/", "/pay/", "/documents/"):
            self.assertIn(prefix, config["never"])

    def test_service_worker_version_changes_with_settings(self):
        before = self.client.get("/sw.js").content
        pwa = PwaSettings.load()
        pwa.offline_title = "بدون اینترنت"
        pwa.save()
        self.assertNotEqual(before, self.client.get("/sw.js").content)

    def test_offline_page(self):
        fa = self.client.get("/fa/offline/")
        self.assertContains(fa, "اتصال اینترنت برقرار نیست")
        self.assertContains(fa, 'content="noindex"')
        self.assertContains(self.client.get("/en/offline/"), "You are offline")

    def test_switched_off(self):
        pwa = PwaSettings.load()
        pwa.enabled = False
        pwa.save()
        self.assertEqual(self.client.get("/fa/manifest.webmanifest").status_code, 404)
        self.assertEqual(self.client.get("/fa/offline/").status_code, 404)
        home = self.client.get("/fa/")
        self.assertNotContains(home, 'rel="manifest"')
        self.assertNotContains(home, "install-banner")
        worker = self.client.get("/sw.js")
        self.assertEqual(worker.status_code, 200)
        self.assertContains(worker, "unregister()")

    def test_no_install_prompt_when_turned_off(self):
        pwa = PwaSettings.load()
        pwa.show_install_prompt = False
        pwa.save()
        home = self.client.get("/fa/")
        self.assertNotContains(home, 'class="install-banner"')
        self.assertContains(home, 'register("/sw.js"')


class CacheHintTests(TestCase):
    """Only pages that look the same for every signed-out visitor may be kept on the phone."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=QUIET)

    def hint(self, url):
        return self.client.get(url).get(CACHE_HINT_HEADER)

    def test_public_pages_are_marked(self):
        self.assertEqual(self.hint("/fa/"), "page")
        self.assertEqual(self.hint("/en/"), "page")
        self.assertEqual(self.hint("/fa/offline/"), "page")

    def test_pages_with_forms_are_not_marked(self):
        self.assertIsNone(self.hint("/fa/contact/"))
        self.assertIsNone(self.hint("/fa/panel/login/"))

    def test_signed_in_visitors_are_not_marked(self):
        user = get_user_model().objects.create_user("member", password="x" * 12)
        self.client.force_login(user)
        self.assertIsNone(self.hint("/fa/"))

    def test_visitors_with_a_session_are_not_marked(self):
        session = self.client.session
        session["cart"] = {"1": 2}
        session.save()
        self.assertIsNone(self.hint("/fa/"))

    def test_private_paths_and_non_html_are_not_marked(self):
        self.assertIsNone(self.hint("/admin/login/"))
        self.assertIsNone(self.hint("/fa/search/?query=x"))
        self.assertIsNone(self.hint("/sw.js"))
        self.assertIsNone(self.hint("/fa/manifest.webmanifest"))
        self.assertIsNone(self.client.head("/fa/").get(CACHE_HINT_HEADER))
