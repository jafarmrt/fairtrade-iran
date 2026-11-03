import io
import time

from django.contrib.auth.models import Group, User
from django.core import mail, signing
from django.core.management import call_command
from django.test import TestCase, override_settings

from core.models import SiteSettings
from members.models import Member
from products.models import Product

from .forms import SIGNER_SALT
from .models import ProducerShare, WholesaleInquiry, WholesalePage, WholesaleSettings, option_lines
from .views import HONEYPOT_FIELD

QUIET = io.StringIO()


def old_token(seconds=60):
    return signing.dumps(time.time() - seconds, salt=SIGNER_SALT)


@override_settings(WAGTAILADMIN_BASE_URL="https://example.org")
class WholesaleTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=QUIET)
        site = SiteSettings.load()
        site.notification_email = "house@example.org"
        site.save()
        cls.armoz = Member.objects.get(slug="armoz")
        cls.other = Member.objects.exclude(pk=cls.armoz.pk).exclude(status__in=Member.INACTIVE_STATUSES).first()
        cls.armoz.public_email = "armoz@example.org"
        cls.armoz.save()
        cls.towel = Product.objects.create(member=cls.armoz, name="حوله", name_en="Hand-woven towel", slug="towel")
        cls.dates = Product.objects.create(member=cls.armoz, name="خرما", name_en="Dates", slug="dates")
        cls.basket = Product.objects.create(member=cls.other, name="سبد", name_en="Basket", slug="basket")
        cls.fa_only = Product.objects.create(member=cls.other, name="فقط فارسی", slug="fa-only")
        cls.manager = User.objects.create_user("armoz", "manager@example.org", "pw-12345")
        cls.armoz.managers.add(cls.manager)
        cls.staff = User.objects.create_user("market", "market@example.org", "pw-12345", is_staff=True)
        cls.staff.groups.add(Group.objects.get(name="کارگروه توسعه بازار"))

    def data(self, **extra):
        values = {
            "company": "Fair Shop GmbH", "contact_name": "Anna Berg", "email": "anna@fairshop.example",
            "phone": "+49 30 1234", "country": "Germany", "city": "Berlin", "website": "https://fairshop.example",
            "buyer_type": "fairtrade", "incoterm": "FOB", "destination": "Hamburg", "needed_by": "March",
            "other_products": "", "message": "Do you have organic certificates?",
            "started": old_token(),
            f"qty_{self.towel.pk}": "200", f"unit_{self.towel.pk}": "pcs",
            f"qty_{self.basket.pk}": "۵۰", f"unit_{self.basket.pk}": "pcs",
        }
        values.update(extra)
        return values

    def post(self, lang="en", **extra):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(f"/{lang}/wholesale/", self.data(**extra))


class SeedAndPageTests(WholesaleTestCase):
    def test_pages_in_both_languages(self):
        fa = WholesalePage.objects.get(locale__language_code="fa")
        en = WholesalePage.objects.get(locale__language_code="en")
        self.assertEqual(en.translation_key, fa.translation_key)
        self.assertTrue(en.show_in_menus)
        self.assertFalse(fa.show_in_menus)
        call_command("seed_content", stdout=QUIET)  # idempotent
        self.assertEqual(WholesalePage.objects.count(), 2)

    def test_handler_groups_get_permissions(self):
        self.assertTrue(self.staff.has_perm("wholesale.change_wholesaleinquiry"))
        secretariat = Group.objects.get(name="دبیرخانه")
        self.assertTrue(secretariat.permissions.filter(codename="view_wholesaleinquiry").exists())

    def test_english_catalogue_hides_products_without_english_name(self):
        response = self.client.get("/en/wholesale/")
        self.assertContains(response, "Hand-woven towel")
        self.assertContains(response, f'name="qty_{self.basket.pk}"')
        self.assertNotContains(response, f'name="qty_{self.fa_only.pk}"')
        self.assertContains(response, "Wholesale and export")  # in the English menu

    def test_persian_catalogue(self):
        response = self.client.get("/fa/wholesale/")
        self.assertContains(response, "حوله")
        self.assertContains(response, f'name="qty_{self.fa_only.pk}"')
        self.assertContains(response, 'dir="rtl"')

    def test_product_page_and_shop_link_to_wholesale(self):
        response = self.client.get("/en/shop/towel/")
        self.assertContains(response, "/en/wholesale/?product=towel")
        self.assertContains(self.client.get("/en/shop/"), "Send a wholesale enquiry")

    def test_preselected_product_is_highlighted(self):
        response = self.client.get("/en/wholesale/?product=towel")
        self.assertContains(response, 'class="wh-item is-selected"')

    def test_option_lines(self):
        self.assertEqual(option_lines("FOB | Free on board | فوب\n\nEXW"),
                         [("FOB", "Free on board", "فوب"), ("EXW", "EXW", "EXW")])


class SubmitTests(WholesaleTestCase):
    def test_enquiry_is_saved_and_routed(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        inquiry = WholesaleInquiry.objects.get()
        self.assertContains(response, inquiry.tracking_code)
        self.assertEqual(inquiry.language, "en")
        self.assertEqual(inquiry.country, "Germany")
        self.assertEqual(inquiry.lines.count(), 2)
        self.assertEqual(inquiry.lines.get(product=self.basket).quantity, 50)  # Persian digits accepted
        self.assertEqual(set(inquiry.producers.values_list("member", flat=True)), {self.armoz.pk, self.other.pk})
        self.assertTrue(inquiry.ip_hash)

        to = {tuple(m.to): m for m in mail.outbox}
        buyer = to[("anna@fairshop.example",)]
        self.assertIn(inquiry.tracking_code, buyer.subject)
        self.assertIn("Hand-woven towel: 200 pieces", buyer.body)
        house = next(m for m in mail.outbox if "house@example.org" in m.to)
        self.assertIn("market@example.org", house.to)
        self.assertEqual(house.reply_to, ["anna@fairshop.example"])
        self.assertIn("Fair Shop GmbH", house.body)
        producer = next(m for m in mail.outbox if "manager@example.org" in m.to)
        self.assertIn("armoz@example.org", producer.to)
        self.assertIn("حوله: 200 عدد", producer.body)
        self.assertNotIn("Basket", producer.body)  # only their own products
        self.assertNotIn("anna@fairshop.example", producer.body)
        self.assertIn("/fa/panel/", producer.body)
        self.assertTrue(inquiry.producers.get(member=self.armoz).notified_at)

    def test_persian_form(self):
        self.post(lang="fa")
        inquiry = WholesaleInquiry.objects.get()
        self.assertEqual(inquiry.language, "fa")
        buyer = next(m for m in mail.outbox if m.to == ["anna@fairshop.example"])
        self.assertIn("درخواست سفارش عمده شما رسید", buyer.subject)

    def test_other_products_only(self):
        self.post(**{f"qty_{self.towel.pk}": "", f"qty_{self.basket.pk}": "", "other_products": "Rugs 2x3 m"})
        inquiry = WholesaleInquiry.objects.get()
        self.assertEqual(inquiry.lines.count(), 0)
        self.assertEqual(inquiry.producers.count(), 0)  # the House refers it by hand

    def test_nothing_requested(self):
        response = self.post(**{f"qty_{self.towel.pk}": "", f"qty_{self.basket.pk}": ""})
        self.assertContains(response, "at least one product")
        self.assertFalse(WholesaleInquiry.objects.exists())

    def test_bad_quantity_is_kept_and_flagged(self):
        response = self.post(**{f"qty_{self.towel.pk}": "lots"})
        self.assertContains(response, "whole numbers")
        self.assertContains(response, 'value="lots"')
        self.assertFalse(WholesaleInquiry.objects.exists())

    def test_required_fields(self):
        response = self.post(email="not-an-email", country="")
        self.assertContains(response, "This field is required.")
        self.assertContains(response, "Enter a valid email address.")
        self.assertFalse(WholesaleInquiry.objects.exists())

    def test_honeypot(self):
        response = self.post(**{HONEYPOT_FIELD: "spam"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(WholesaleInquiry.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_website_field_is_not_the_honeypot(self):
        self.post(website="https://fairshop.example")
        self.assertTrue(WholesaleInquiry.objects.exists())

    def test_too_fast_or_missing_token(self):
        self.post(started=old_token(seconds=1))
        self.post(started="forged")
        self.assertFalse(WholesaleInquiry.objects.exists())

    def test_rate_limit(self):
        s = WholesaleSettings.load()
        s.max_per_hour = 2
        s.save()
        for _ in range(3):
            response = self.post()
        self.assertEqual(WholesaleInquiry.objects.count(), 2)
        self.assertContains(response, "many enquiries")

    def test_closed(self):
        s = WholesaleSettings.load()
        s.enabled = False
        s.save()
        response = self.post()
        self.assertContains(response, "not taking wholesale enquiries")
        self.assertNotContains(response, f'name="qty_{self.towel.pk}"')
        self.assertFalse(WholesaleInquiry.objects.exists())

    def test_without_automatic_producer_notice(self):
        s = WholesaleSettings.load()
        s.notify_producers = False
        s.save()
        self.post()
        self.assertEqual(ProducerShare.objects.count(), 0)
        self.assertFalse(any("manager@example.org" in m.to for m in mail.outbox))


class PanelTests(WholesaleTestCase):
    def setUp(self):
        self.post()
        self.inquiry = WholesaleInquiry.objects.get()
        self.share = self.inquiry.producers.get(member=self.armoz)
        mail.outbox.clear()
        self.client.force_login(self.manager)

    def test_list_and_dashboard(self):
        response = self.client.get(f"/fa/panel/{self.armoz.pk}/wholesale/")
        self.assertContains(response, self.inquiry.tracking_code)
        self.assertContains(response, "حوله")
        self.assertNotContains(response, "سبد")
        self.assertContains(self.client.get("/fa/panel/"), "درخواست سفارش عمده منتظر پاسخ شماست")

    def test_detail_hides_buyer_contact_by_default(self):
        response = self.client.get(f"/en/panel/{self.armoz.pk}/wholesale/{self.share.pk}/")
        self.assertContains(response, "Germany")
        self.assertContains(response, "FOB")
        self.assertNotContains(response, "anna@fairshop.example")
        self.share.refresh_from_db()
        self.assertEqual(self.share.status, "seen")

    def test_detail_shows_contact_when_allowed(self):
        s = WholesaleSettings.load()
        s.share_buyer_contact = True
        s.save()
        response = self.client.get(f"/en/panel/{self.armoz.pk}/wholesale/{self.share.pk}/")
        self.assertContains(response, "anna@fairshop.example")

    def test_reply(self):
        url = f"/fa/panel/{self.armoz.pk}/wholesale/{self.share.pk}/"
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, {"status": "quoted", "price_quote": "EUR 9 / piece",
                                              "lead_time": "6 weeks", "reply": "Samples available"})
        self.assertRedirects(response, f"/fa/panel/{self.armoz.pk}/wholesale/")
        self.share.refresh_from_db()
        self.assertEqual(self.share.status, "quoted")
        self.assertEqual(self.share.replied_by, self.manager)
        house = next(m for m in mail.outbox if "house@example.org" in m.to)
        self.assertIn("EUR 9 / piece", house.body)

    def test_cannot_see_other_members_share(self):
        other_share = self.inquiry.producers.get(member=self.other)
        response = self.client.get(f"/fa/panel/{self.armoz.pk}/wholesale/{other_share.pk}/")
        self.assertEqual(response.status_code, 404)
        response = self.client.get(f"/fa/panel/{self.other.pk}/wholesale/")
        self.assertEqual(response.status_code, 404)

    def test_closed_enquiry_cannot_be_answered(self):
        self.inquiry.status = "closed"
        self.inquiry.save()
        response = self.client.get(f"/fa/panel/{self.armoz.pk}/wholesale/{self.share.pk}/")
        self.assertContains(response, "این درخواست بسته شده است")
        self.client.post(f"/fa/panel/{self.armoz.pk}/wholesale/{self.share.pk}/", {"status": "declined"})
        self.share.refresh_from_db()
        self.assertNotEqual(self.share.status, "declined")

    def test_spam_is_hidden(self):
        self.inquiry.status = "spam"
        self.inquiry.save()
        response = self.client.get(f"/fa/panel/{self.armoz.pk}/wholesale/")
        self.assertNotContains(response, self.inquiry.tracking_code)


class AdminTests(WholesaleTestCase):
    def test_admin_list_and_manual_referral(self):
        self.post(**{f"qty_{self.towel.pk}": "", f"qty_{self.basket.pk}": "", "other_products": "Rugs"})
        inquiry = WholesaleInquiry.objects.get()
        mail.outbox.clear()
        self.client.force_login(self.staff)
        response = self.client.get("/admin/wholesale_inquiries/")
        self.assertContains(response, inquiry.tracking_code)
        response = self.client.get(f"/admin/wholesale_inquiries/edit/{inquiry.pk}/")
        self.assertEqual(response.status_code, 200)

        ProducerShare.objects.create(inquiry=inquiry, member=self.armoz)
        from .notifications import notify_new_shares

        notify_new_shares(inquiry)
        producer = next(m for m in mail.outbox if "manager@example.org" in m.to)
        self.assertIn("Rugs", producer.body)
        mail.outbox.clear()
        notify_new_shares(inquiry)  # only once
        self.assertEqual(mail.outbox, [])

    def test_members_cannot_open_admin_list(self):
        self.client.force_login(self.manager)
        response = self.client.get("/admin/wholesale_inquiries/")
        self.assertNotEqual(response.status_code, 200)
