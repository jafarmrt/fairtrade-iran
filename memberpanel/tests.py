import io
import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image as PILImage

from members.models import Member
from membership.models import MembershipApplication, Status
from membership.workflow import status_entered
from products.models import Product

from .models import PanelSettings
from .text import html_to_text, text_to_html

QUIET = io.StringIO()
MEDIA = tempfile.mkdtemp()


def png(name="photo.png"):
    buf = io.BytesIO()
    PILImage.new("RGB", (40, 30), (200, 150, 40)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA, WAGTAILADMIN_BASE_URL="https://example.org")
class PanelTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=QUIET)
        cls.member = Member.objects.get(slug="armoz")
        cls.user = User.objects.create_user("maryam", "maryam@example.org", "pw-12345")
        cls.member.managers.add(cls.user)
        cls.other = Member.objects.exclude(pk=cls.member.pk).first()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def login(self):
        self.client.force_login(self.user)

    def product_data(self, **extra):
        data = {"name": "حصیر", "name_en": "Mat", "summary": "", "summary_en": "", "price": "",
                "price_note": "", "price_note_en": "", "in_stock": "on", "purchase_url": "",
                "is_published": "on", "description_text": "پاراگراف یک\n\nپاراگراف دو", "description_en_text": ""}
        data.update(extra)
        return data


class AccessTests(PanelTestCase):
    def test_login_required(self):
        response = self.client.get("/fa/panel/")
        self.assertRedirects(response, "/fa/panel/login/?next=/fa/panel/", fetch_redirect_response=False)

    def test_login_with_email(self):
        response = self.client.post("/en/panel/login/", {"username": "MARYAM@example.org", "password": "pw-12345"})
        self.assertRedirects(response, "/en/panel/", fetch_redirect_response=False)

    def test_managers_join_members_group(self):
        self.assertTrue(self.user.groups.filter(name="اعضا").exists())

    def test_dashboard_lists_managed_members_only(self):
        self.login()
        for lang in ("fa", "en"):
            response = self.client.get(f"/{lang}/panel/")
            self.assertContains(response, self.member.tr("name"))
            self.assertNotContains(response, f"/panel/{self.other.pk}/profile/")

    def test_cannot_edit_other_members(self):
        self.login()
        self.assertEqual(self.client.get(f"/fa/panel/{self.other.pk}/profile/").status_code, 404)
        product = Product.objects.create(member=self.other, name="دیگری")
        self.assertEqual(self.client.get(f"/fa/panel/{self.member.pk}/products/{product.pk}/").status_code, 404)

    def test_suspended_member_cannot_edit(self):
        Member.objects.filter(pk=self.member.pk).update(status=Member.SUSPENDED)
        self.login()
        response = self.client.get(f"/fa/panel/{self.member.pk}/profile/")
        self.assertRedirects(response, "/fa/panel/", fetch_redirect_response=False)

    def test_panel_can_be_switched_off(self):
        settings = PanelSettings.load()
        settings.enabled = False
        settings.save()
        self.login()
        self.assertEqual(self.client.get("/fa/panel/").status_code, 503)

    def test_language_switch_stays_in_panel(self):
        self.login()
        response = self.client.get("/fa/panel/")
        self.assertContains(response, 'href="/en/panel/"')


class ProfileTests(PanelTestCase):
    def test_edit_profile_and_upload_logo(self):
        self.login()
        data = {"name": "ارموز", "name_en": "Armoz", "region": self.member.region_id, "city": "میناب",
                "city_en": "Minab", "summary": "خلاصه تازه", "summary_en": "New summary",
                "story_text": "خط یک\n\nخط <دو>", "story_en_text": "",
                "instagram_url": "https://instagram.com/armoz", "website_url": "", "public_phone": "",
                "public_email": "", "logo_upload": png()}
        response = self.client.post(f"/fa/panel/{self.member.pk}/profile/", data)
        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(pk=self.member.pk)
        self.assertEqual(member.summary, "خلاصه تازه")
        self.assertEqual(member.story, "<p>خط یک</p><p>خط &lt;دو&gt;</p>")
        self.assertEqual(member.logo.collection.name, "تصاویر اعضا")
        # Fields the secretariat controls are untouched
        self.assertEqual((member.status, member.is_published), (self.member.status, self.member.is_published))

    def test_untouched_rich_text_keeps_formatting(self):
        Member.objects.filter(pk=self.member.pk).update(story='<h2>تیتر</h2><p><b>پررنگ</b></p>')
        self.login()
        page = self.client.get(f"/fa/panel/{self.member.pk}/profile/")
        form = page.context["form"]
        data = {k: (v if v is not None else "") for k, v in form.initial.items() if k in form.fields}
        data.update({"story_text": form.fields["story_text"].initial, "story_en_text": "", "region": self.member.region_id})
        data = {k: v for k, v in data.items() if not k.endswith("upload") and k not in ("logo", "cover_image")}
        self.client.post(f"/fa/panel/{self.member.pk}/profile/", data)
        self.assertEqual(Member.objects.get(pk=self.member.pk).story, '<h2>تیتر</h2><p><b>پررنگ</b></p>')


class ProductTests(PanelTestCase):
    def test_new_product_waits_for_review_and_notifies(self):
        settings = PanelSettings.load()
        settings.review_email = "shop@example.org"
        settings.save()
        self.login()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f"/fa/panel/{self.member.pk}/products/new/",
                                        self.product_data(new_images=[png("a.png"), png("b.png")]))
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name="حصیر")
        self.assertTrue(product.needs_review)
        self.assertEqual(product.member, self.member)
        self.assertEqual(product.images.count(), 2)
        self.assertEqual(product.description, "<p>پاراگراف یک</p><p>پاراگراف دو</p>")
        self.assertNotIn(product, Product.visible())
        self.assertTrue(any("حصیر" in m.subject and m.to == ["shop@example.org"] for m in mail.outbox))

        product.needs_review = False
        product.save()
        self.assertIn(product, Product.visible())

    def test_without_review_products_go_live(self):
        settings = PanelSettings.load()
        settings.new_products_need_review = False
        settings.save()
        self.login()
        self.client.post(f"/en/panel/{self.member.pk}/products/new/", self.product_data())
        self.assertIn(Product.objects.get(name="حصیر"), Product.visible())

    def test_image_limit(self):
        settings = PanelSettings.load()
        settings.max_images_per_product = 1
        settings.save()
        self.login()
        response = self.client.post(f"/fa/panel/{self.member.pk}/products/new/",
                                    self.product_data(new_images=[png("a.png"), png("b.png")]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(name="حصیر").exists())

    def test_edit_remove_image_and_delete(self):
        self.login()
        self.client.post(f"/fa/panel/{self.member.pk}/products/new/", self.product_data(new_images=[png()]))
        product = Product.objects.get(name="حصیر")
        image_id = product.images.get().pk
        self.client.post(f"/fa/panel/{self.member.pk}/products/{product.pk}/",
                         self.product_data(name="حصیر بزرگ", in_stock="", remove_image=[image_id]))
        product.refresh_from_db()
        self.assertEqual((product.name, product.in_stock, product.images.count()), ("حصیر بزرگ", False, 0))
        self.assertTrue(product.needs_review)  # editing does not skip the review

        self.client.post(f"/fa/panel/{self.member.pk}/products/{product.pk}/delete/")
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_delete_can_be_disabled(self):
        settings = PanelSettings.load()
        settings.allow_delete_products = False
        settings.save()
        product = Product.objects.create(member=self.member, name="ماندگار")
        self.login()
        response = self.client.post(f"/fa/panel/{self.member.pk}/products/{product.pk}/delete/")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())


class OnboardingTests(PanelTestCase):
    def application(self, **extra):
        values = dict(member_type="producer", name="کارگاه تازه", name_en="New Workshop",
                      contact_person="زهرا", email="Zahra@Example.org", phone="0912", city="کرمان",
                      website="https://new.example.org", language="en")
        values.update(extra)
        return MembershipApplication.objects.create(**values)

    def test_trial_creates_hidden_profile_account_and_invite(self):
        application = self.application()
        with self.captureOnCommitCallbacks(execute=True):
            status_entered.send(sender=MembershipApplication, application=application, status=Status.TRIAL)
        member = Member.objects.get(application=application)
        self.assertEqual((member.status, member.is_published, member.name_en), (Member.TRIAL, False, "New Workshop"))
        self.assertEqual(member.website_url, "https://new.example.org")
        user = member.managers.get()
        self.assertEqual(user.email, "zahra@example.org")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.groups.filter(name="اعضا").exists())
        invite = mail.outbox[-1]
        self.assertEqual(invite.to, ["zahra@example.org"])
        self.assertIn("https://example.org/en/panel/password/set/", invite.body)

        # The invitation link lets the new member choose a password and sign in
        link = next(line for line in invite.body.splitlines() if "/password/set/" in line)
        response = self.client.get(link.replace("https://example.org", ""), follow=True)
        response = self.client.post(response.redirect_chain[-1][0],
                                    {"new_password1": "a-Long-pass-987", "new_password2": "a-Long-pass-987"})
        self.assertRedirects(response, "/en/panel/password/set/done/", fetch_redirect_response=False)
        self.assertTrue(self.client.login(username="zahra@example.org", password="a-Long-pass-987"))

        # Registration as a full member updates the same profile without a second invite
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            status_entered.send(sender=MembershipApplication, application=application, status=Status.MEMBER)
        member.refresh_from_db()
        self.assertEqual(member.status, Member.OFFICIAL)
        self.assertEqual(Member.objects.filter(application=application).count(), 1)
        self.assertEqual(mail.outbox, [])

    def test_not_accepted_suspends_and_hides(self):
        application = self.application()
        status_entered.send(sender=MembershipApplication, application=application, status=Status.TRIAL)
        Member.objects.filter(application=application).update(is_published=True)
        status_entered.send(sender=MembershipApplication, application=application, status=Status.NOT_ACCEPTED)
        member = Member.objects.get(application=application)
        self.assertEqual((member.status, member.is_published), (Member.SUSPENDED, False))

    def test_settings_control_onboarding(self):
        settings = PanelSettings.load()
        settings.create_profile_on_trial = False
        settings.invite_new_members = False
        settings.publish_new_profiles = True
        settings.save()
        application = self.application(email="x@example.org")
        status_entered.send(sender=MembershipApplication, application=application, status=Status.TRIAL)
        self.assertFalse(Member.objects.filter(application=application).exists())
        status_entered.send(sender=MembershipApplication, application=application, status=Status.MEMBER)
        member = Member.objects.get(application=application)
        self.assertTrue(member.is_published)
        self.assertFalse(member.managers.exists())

    def test_password_reset_reaches_accounts_without_password(self):
        User.objects.create(username="nopw", email="nopw@example.org", password="!")
        self.client.post("/fa/panel/password/reset/", {"email": "nopw@example.org"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/fa/panel/password/set/", mail.outbox[0].body)


class TextTests(TestCase):
    def test_round_trip(self):
        self.assertEqual(html_to_text("<p>a<br/>b</p><p>c &amp; d</p>"), "a\nb\n\nc & d")
        self.assertEqual(text_to_html("a\nb\n\nc & d"), "<p>a<br/>b</p><p>c &amp; d</p>")
        self.assertEqual(text_to_html("  "), "")
