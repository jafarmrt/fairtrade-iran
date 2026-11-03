import datetime
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import MembershipSettings
from members.models import Member
from membership.models import MembershipApplication
from membership.tests import MembershipTestCase
from standing.models import Dues

from .gateways import Idpay, Zarinpal
from .models import Payment, PaymentSettings
from .services import complete


def enable(provider="test", **flags):
    config = PaymentSettings.load()
    config.enabled = True
    config.provider = provider
    config.merchant_id = "merchant-123"
    for k, v in flags.items():
        setattr(config, k, v)
    config.save()
    return config


class SettingsTests(TestCase):
    def test_off_by_default(self):
        config = PaymentSettings.load()
        self.assertFalse(config.enabled)
        self.assertFalse(config.enabled_for("order"))
        enable(for_dues=False)
        config = PaymentSettings.load()
        self.assertTrue(config.enabled_for("order"))
        self.assertFalse(config.enabled_for("dues"))

    @override_settings(PAYMENT_MERCHANT_ID="from-env")
    def test_merchant_from_environment(self):
        self.assertEqual(enable().effective_merchant_id, "from-env")


class FakePayment:
    def __init__(self, amount=1_000_000):
        import uuid

        self.uid, self.amount, self.authority = uuid.uuid4(), amount, ""
        self.mobile, self.email, self.description = "0912", "a@b.c", "test"


class ZarinpalTests(TestCase):
    def test_request_and_verify(self):
        gw = Zarinpal(enable("zarinpal"))
        p = FakePayment()
        with mock.patch("payments.gateways.post_json",
                        return_value=(200, {"data": {"code": 100, "authority": "A0001"}, "errors": []})) as post:
            url = gw.request(p, "https://example.org/pay/x/return/")
        self.assertEqual(url, "https://payment.zarinpal.com/pg/StartPay/A0001")
        sent = post.call_args.args[1]
        self.assertEqual((sent["amount"], sent["currency"], sent["merchant_id"]), (1_000_000, "IRR", "merchant-123"))
        with mock.patch("payments.gateways.post_json",
                        return_value=(200, {"data": {"code": 100, "ref_id": 778899, "card_pan": "6037**1234"}})):
            result = gw.verify(p, {"Authority": "A0001", "Status": "OK"})
        self.assertTrue(result.ok)
        self.assertEqual(result.ref_id, "778899")
        self.assertFalse(gw.verify(p, {"Authority": "A0001", "Status": "NOK"}).ok)

    def test_sandbox_host(self):
        self.assertIn("sandbox.zarinpal.com", Zarinpal(enable("zarinpal", sandbox=True)).host)


class IdpayTests(TestCase):
    def test_request_and_verify(self):
        gw = Idpay(enable("idpay"))
        p = FakePayment()
        with mock.patch("payments.gateways.post_json",
                        return_value=(201, {"id": "idp-1", "link": "https://idpay.ir/p/ws/idp-1"})):
            self.assertEqual(gw.request(p, "https://example.org/cb"), "https://idpay.ir/p/ws/idp-1")
        params = {"status": "10", "id": "idp-1", "order_id": str(p.uid)}
        with mock.patch("payments.gateways.post_json", return_value=(200, {
                "status": 100, "track_id": 5555, "amount": 1_000_000, "payment": {"card_no": "603799******1234"}})):
            result = gw.verify(p, params)
        self.assertEqual((result.ok, result.ref_id), (True, "5555"))
        with mock.patch("payments.gateways.post_json", return_value=(200, {"status": 100, "amount": 1})):
            self.assertFalse(gw.verify(p, params).ok)  # amount mismatch


class TestGatewayGuardTests(MembershipTestCase):
    @override_settings(DEBUG=False, PAYMENT_ALLOW_TEST_GATEWAY=False)
    def test_test_gateway_refused_on_live_site(self):
        enable("test")
        application = self.submit_producer()
        self.client.post("/fa/membership/apply-done/", {"step": "pay_fee"})
        payment = Payment.objects.get()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        application.refresh_from_db()
        self.assertFalse(application.fee_confirmed)


@override_settings(DEBUG=True)
class ApplicationFeeTests(MembershipTestCase):
    def test_receipt_optional_and_pay_after_submitting(self):
        enable("test")
        application = self.submit_producer(receipt="", payment_reference="")
        page = self.client.get("/fa/membership/apply-done/")
        self.assertContains(page, "پرداخت هزینه درخواست")
        response = self.client.post("/fa/membership/apply-done/", {"step": "pay_fee"})
        payment = Payment.objects.get()
        self.assertEqual((payment.purpose, payment.amount), ("application_fee", 5_000_000))
        self.assertRedirects(response, f"/pay/{payment.uid}/test-gateway/", fetch_redirect_response=False)
        self.assertEqual(self.client.get(f"/pay/{payment.uid}/test-gateway/").status_code, 200)
        response = self.client.post(f"/pay/{payment.uid}/return/", {"result": "ok", "authority": payment.authority})
        self.assertRedirects(response, "/fa/membership/apply-done/?payment=ok", fetch_redirect_response=False)
        application.refresh_from_db()
        self.assertTrue(application.fee_confirmed)
        self.assertIn("آنلاین", application.payment_reference)
        self.assertTrue(application.events.filter(action="fee_paid_online").exists())
        self.assertNotContains(self.client.get("/fa/membership/apply-done/"), 'value="pay_fee"')

    def test_receipt_still_required_when_online_is_off(self):
        response = self.client.post("/fa/membership/apply/producer/", self.producer_post(receipt=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MembershipApplication.objects.exists())

    def test_cancelled_payment(self):
        enable("test")
        application = self.submit_producer()
        self.client.post("/fa/membership/apply-done/", {"step": "pay_fee"})
        payment = Payment.objects.get()
        response = self.client.post(f"/pay/{payment.uid}/return/", {"result": "cancel", "authority": payment.authority})
        self.assertRedirects(response, "/fa/membership/apply-done/?payment=failed", fetch_redirect_response=False)
        application.refresh_from_db()
        self.assertFalse(application.fee_confirmed)
        self.assertEqual(Payment.objects.get().status, Payment.Status.FAILED)

    def test_gateway_down_falls_back_to_receipt(self):
        enable("zarinpal")
        self.submit_producer(receipt="", payment_reference="")
        with mock.patch("payments.gateways.urllib.request.urlopen", side_effect=OSError("no route")):
            response = self.client.post("/fa/membership/apply-done/", {"step": "pay_fee"}, follow=True)
        self.assertContains(response, "درگاه پرداخت الان در دسترس نیست")
        self.assertEqual(Payment.objects.get().status, Payment.Status.FAILED)

    def test_verify_unreachable_leaves_payment_open(self):
        enable("zarinpal")
        self.submit_producer()
        with mock.patch("payments.gateways.post_json",
                        return_value=(200, {"data": {"code": 100, "authority": "A9"}})):
            self.client.post("/fa/membership/apply-done/", {"step": "pay_fee"})
        payment = Payment.objects.get()
        from .gateways import GatewayError

        with mock.patch("payments.gateways.post_json", side_effect=GatewayError("timeout")):
            complete(payment, {"Authority": "A9", "Status": "OK"})
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.STARTED)


    def test_stray_return_does_not_fail_the_payment(self):
        """A reload or link preview of the return URL must not block the real return from the bank."""
        enable("zarinpal")
        self.submit_producer()
        with mock.patch("payments.gateways.post_json",
                        return_value=(200, {"data": {"code": 100, "authority": "A7"}})):
            self.client.post("/fa/membership/apply-done/", {"step": "pay_fee"})
        payment = Payment.objects.get()
        complete(payment, {})
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.STARTED)
        with mock.patch("payments.gateways.post_json",
                        return_value=(200, {"data": {"code": 100, "ref_id": 55, "card_pan": None}})):
            complete(payment, {"Authority": "A7", "Status": "OK"})
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.ref_id, payment.card), (Payment.Status.PAID, "55", ""))


@override_settings(DEBUG=True, PRIVATE_MEDIA_ROOT=tempfile.mkdtemp())
class DuesOnlineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        import io

        call_command("seed_content", stdout=io.StringIO())
        ms = MembershipSettings.load()
        ms.annual_fee_producer = 5_000_000
        ms.save()
        cls.member = Member.objects.get(slug="armoz")
        Member.objects.filter(pk=cls.member.pk).update(status=Member.OFFICIAL)
        cls.user = User.objects.create_user("maryam", "maryam@example.org", "pw-12345")
        cls.member.managers.add(cls.user)
        today = datetime.date.today()
        cls.dues = Dues.objects.create(member=cls.member, year=1405, period_start=today, due_date=today,
                                       amount=5_000_000)

    def test_pay_dues_online_from_panel(self):
        enable("test")
        self.client.force_login(self.user)
        url = f"/fa/panel/{self.member.pk}/membership/"
        self.assertContains(self.client.get(url), "پرداخت حق عضویت سال")
        self.client.post(url, {"step": "pay_dues", "dues": self.dues.pk})
        payment = Payment.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/pay/{payment.uid}/return/", {"result": "ok", "authority": payment.authority})
        self.dues.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(self.dues.status, Dues.Status.PAID)
        record = self.dues.payments.get()
        self.assertEqual((record.status, record.reference), ("confirmed", payment.ref_id))

    def test_no_button_when_off(self):
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(f"/fa/panel/{self.member.pk}/membership/"), 'value="pay_dues"')
