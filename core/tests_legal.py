"""Legal pages in the footer and at checkout, WebP renditions, and bilingual shop errors."""

import io
import shutil
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import translation

from core.models import SiteSettings
from shop.services import OrderError

QUIET = io.StringIO()


class LegalPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=QUIET)

    def test_seeded_and_linked_in_both_languages(self):
        s = SiteSettings.load()
        self.assertIsNotNone(s.privacy_page)
        self.assertFalse(s.privacy_page.show_in_menus)
        fa = self.client.get("/fa/")
        self.assertContains(fa, "حریم خصوصی")
        self.assertContains(fa, "شرایط بازگشت کالا")
        en = self.client.get("/en/")
        self.assertContains(en, "Privacy")
        self.assertContains(en, 'href="/en/terms/"')
        self.assertContains(self.client.get("/en/returns/"), "Refunds")

    def test_seed_is_idempotent_and_keeps_staff_choice(self):
        s = SiteSettings.load()
        about = s.terms_page.get_parent().get_children().get(slug="about")
        s.terms_page = about
        s.save()
        call_command("seed_content", stdout=QUIET)
        self.assertEqual(SiteSettings.load().terms_page_id, about.pk)

    def test_unpublished_page_is_not_linked(self):
        s = SiteSettings.load()
        s.privacy_page.unpublish()
        self.assertNotContains(self.client.get("/fa/"), 'href="/fa/privacy/"')


MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class WebpTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def test_renditions_are_webp_but_share_images_are_jpeg(self):
        from django.conf import settings

        self.assertEqual(settings.WAGTAILIMAGES_FORMAT_CONVERSIONS["jpeg"], "webp")
        from wagtail.images.tests.utils import get_test_image_file
        from wagtail.images.models import Image

        image = Image.objects.create(title="x", file=get_test_image_file())
        self.assertTrue(image.get_rendition("fill-100x100").url.endswith(".webp"))
        self.assertTrue(image.get_rendition("fill-1200x630|format-jpeg").url.endswith(".jpg"))


class OrderErrorTests(TestCase):
    def test_message_in_page_language(self):
        error = OrderError("فارسی", "English")
        with translation.override("en"):
            self.assertEqual(str(error), "English")
        with translation.override("fa"):
            self.assertEqual(str(error), "فارسی")
        with translation.override("en"):
            self.assertEqual(str(OrderError("فقط فارسی")), "فقط فارسی")
