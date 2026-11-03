import io

from django.core.files.images import ImageFile
from django.core.management import call_command
from django.test import TestCase
from PIL import Image as PILImage
from wagtail.images.models import Image
from wagtail.models import Locale

from pages import principles
from pages.models import PrinciplesPage


class PrincipleColoursTests(TestCase):
    """Each principle shows WFTO's colour and an icon, unless the admin picked others."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=io.StringIO())

    def page(self, lang="fa"):
        return PrinciplesPage.objects.get(locale=Locale.objects.get(language_code=lang))

    def test_defaults_follow_wfto_order(self):
        response = self.client.get("/fa/principles/")
        content = response.content.decode()
        positions = [content.find(f"--principle-colour:{c}") for c in principles.WFTO_COLOURS]
        self.assertNotIn(-1, positions)
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(content.count('class="principle__icon"'), 10)
        self.assertContains(response, "اصل ۱۰")
        self.assertContains(self.client.get("/en/principles/"), "Principle 10")

    def test_admin_colour_and_icon_choice(self):
        p = self.page().principles.first()
        p.colour = "#123456"
        p.icon_key = "environment"
        p.save()
        response = self.client.get("/fa/principles/")
        self.assertContains(response, "--principle-colour:#123456")
        self.assertContains(response, principles.ICONS["environment"][1], count=2)

    def test_uploaded_icon_replaces_drawing(self):
        buf = io.BytesIO()
        PILImage.new("RGBA", (64, 64), (255, 255, 255, 0)).save(buf, "PNG")
        image = Image.objects.create(title="WFTO 1", file=ImageFile(buf, name="wfto-1.png"))
        p = self.page().principles.first()
        p.icon = image
        p.save()
        response = self.client.get("/fa/principles/")
        self.assertContains(response, "principle__icon--image")
        self.assertNotContains(response, principles.ICONS["opportunity"][1])

    def test_readable_ink_on_every_colour(self):
        for colour in principles.WFTO_COLOURS:
            ink = principles.ink_for(colour)
            bg, fg = principles._luminance(colour), principles._luminance(ink)
            ratio = (max(bg, fg) + 0.05) / (min(bg, fg) + 0.05)
            self.assertGreaterEqual(ratio, 3, colour)  # icons are graphics: 3:1
