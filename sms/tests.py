import json
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.core.management import call_command
from django.test import TestCase, override_settings

from membership.tests import MembershipTestCase
from membership.workflow import perform

from . import notify, notify_role
from .backends import KavenegarBackend, SmsError, SmsIrBackend, outbox
from .models import SmsLog, SmsSettings, SmsTemplate
from .phone import mobile_list, normalize_mobile
from .registry import EVENTS

LOCMEM = "sms.backends.LocmemBackend"


def enable(**extra):
    config = SmsSettings.load()
    config.enabled = True
    config.secretariat_mobiles = "09120000001"
    config.commission_mobiles = "09120000002, ۰۹۱۲۰۰۰۰۰۰۳"
    for key, value in extra.items():
        setattr(config, key, value)
    config.save()
    return config


class PhoneTests(TestCase):
    def test_normalize(self):
        for raw in ["09121234567", "+989121234567", "00989121234567", "989121234567", "9121234567",
                    "۰۹۱۲ ۱۲۳ ۴۵۶۷", "0912-123-4567"]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_mobile(raw), "09121234567")
        for raw in ["", None, "02188776655", "+4915112345678", "0912123"]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_mobile(raw), "")

    def test_list(self):
        self.assertEqual(mobile_list("09121234567، 09121234567\n+989350000000, bad"),
                         ["09121234567", "09350000000"])


@override_settings(SMS_BACKEND=LOCMEM)
class ServiceTests(TestCase):
    def setUp(self):
        outbox.clear()
        call_command("seed_content", stdout=open("/dev/null", "w"))

    def test_seed_creates_templates_once(self):
        self.assertEqual(SmsTemplate.objects.count(), len(EVENTS))
        SmsTemplate.objects.filter(event="membership_received").update(text="ویرایش‌شده")
        call_command("seed_content", stdout=open("/dev/null", "w"))
        self.assertEqual(SmsTemplate.objects.get(event="membership_received").text, "ویرایش‌شده")

    def test_disabled_by_default(self):
        self.assertFalse(SmsSettings.load().enabled)
        self.assertEqual(notify("membership_received", "09121234567", {"name": "x"}), 0)
        self.assertEqual(outbox, [])

    def test_renders_template_in_language(self):
        enable()
        notify("membership_received", "+989121234567", {"name": "زهرا", "code": "FT-1"})
        self.assertEqual(outbox[-1]["to"], ["09121234567"])
        self.assertIn("زهرا گرامی", outbox[-1]["text"])
        self.assertIn("FT-1", outbox[-1]["text"])
        notify("membership_received", "09121234567", {"name": "Sara", "code": "FT-2"}, lang="en")
        self.assertIn("Dear Sara", outbox[-1]["text"])
        self.assertIn("{site_name}", SmsTemplate.objects.get(event="membership_received").text)
        self.assertTrue(SmsLog.objects.filter(event="membership_received", success=True).exists())

    def test_inactive_template_and_bad_number_send_nothing(self):
        enable()
        SmsTemplate.objects.filter(event="membership_received").update(active=False)
        self.assertEqual(notify("membership_received", "09121234567", {}), 0)
        SmsTemplate.objects.filter(event="membership_received").update(active=True)
        self.assertEqual(notify("membership_received", "021-88776655", {}), 0)
        self.assertEqual(notify("no_such_event", "09121234567", {}), 0)
        self.assertEqual(outbox, [])

    def test_role_numbers_come_from_settings(self):
        enable()
        self.assertEqual(notify_role("complaint_new", "commission", {"code": "ABC"}), 2)
        self.assertEqual(outbox[-1]["to"], ["09120000002", "09120000003"])

    def test_backend_failure_is_logged_not_raised(self):
        enable()
        with mock.patch("sms.backends.LocmemBackend.send", side_effect=SmsError("اعتبار کافی نیست")), \
                self.assertLogs("sms.service", "WARNING"):
            self.assertEqual(notify("membership_received", "09121234567", {"name": "x"}), 0)
        log = SmsLog.objects.get()
        self.assertFalse(log.success)
        self.assertIn("اعتبار", log.error)


class ProviderTests(TestCase):
    def response(self, payload):
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps(payload).encode()
        resp.__enter__.return_value = resp
        return resp

    def test_kavenegar(self):
        config = SmsSettings(provider="kavenegar", api_key="KEY/1", sender="10004346")
        with mock.patch("urllib.request.urlopen", return_value=self.response({"return": {"status": 200}})) as m:
            KavenegarBackend(config).send(["09121234567", "09350000000"], "سلام")
        req = m.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.kavenegar.com/v1/KEY%2F1/sms/send.json")
        self.assertIn(b"receptor=09121234567%2C09350000000", req.data)
        with mock.patch("urllib.request.urlopen",
                        return_value=self.response({"return": {"status": 418, "message": "اعتبار کافی نیست"}})):
            with self.assertRaisesMessage(SmsError, "اعتبار"):
                KavenegarBackend(config).send(["09121234567"], "سلام")

    def test_smsir(self):
        config = SmsSettings(provider="smsir", api_key="KEY", sender="30007732")
        with mock.patch("urllib.request.urlopen", return_value=self.response({"status": 1})) as m:
            SmsIrBackend(config).send(["09121234567"], "سلام")
        req = m.call_args[0][0]
        self.assertEqual(req.get_header("X-api-key"), "KEY")
        self.assertEqual(json.loads(req.data), {"lineNumber": 30007732, "messageText": "سلام",
                                                "mobiles": ["09121234567"]})

    def test_missing_credentials(self):
        with self.assertRaisesMessage(SmsError, "کلید API"):
            SmsIrBackend(SmsSettings(provider="smsir")).send(["09121234567"], "x")

    @override_settings(SMS_API_KEY="FROM-ENV")
    def test_env_key_wins(self):
        self.assertEqual(SmsSettings(api_key="db").effective_api_key, "FROM-ENV")


@override_settings(SMS_BACKEND=LOCMEM)
class MembershipSmsTests(MembershipTestCase):
    def setUp(self):
        outbox.clear()
        enable()

    def test_applicant_and_staff_get_sms_through_the_workflow(self):
        application = self.submit_producer()
        received = [m for m in outbox if m["to"] == ["09120000000"]]
        self.assertTrue(received and application.tracking_code in received[0]["text"])
        self.assertTrue(any(m["to"] == ["09120000001"] and "درخواست عضویت تازه" in m["text"] for m in outbox))

        outbox.clear()
        perform(application, "confirm_fee", self.secretary)
        with self.captureOnCommitCallbacks(execute=True):
            perform(application, "to_commission", self.secretary)
        self.assertTrue(any(m["to"] == ["09120000002", "09120000003"] for m in outbox))
        self.assertTrue(any(m["to"] == ["09120000000"] and "کمیسیون" in m["text"] for m in outbox))

    def test_no_sms_when_disabled(self):
        enable(enabled=False)
        self.submit_producer()
        self.assertEqual(outbox, [])


@override_settings(SMS_BACKEND=LOCMEM)
class ContactSmsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=open("/dev/null", "w"))

    def setUp(self):
        outbox.clear()
        enable()

    def contact_post(self):
        form = self.client.get("/fa/contact/").context["form"]
        data = {name: "a@example.org" if f.__class__.__name__ == "EmailField" else "سلام"
                for name, f in form.fields.items()}
        return self.client.post("/fa/contact/", data)

    def complaint_data(self):
        return {"relation": "buyer", "subject_of_complaint": "یک تولیدکننده", "category": "product",
                "description": "متن محرمانه شکایت"}

    def test_complaint_sms_has_code_but_no_details(self):
        self.client.post("/fa/complaint/", self.complaint_data())
        self.assertEqual(outbox[-1]["to"], ["09120000002", "09120000003"])
        self.assertNotIn("متن محرمانه", outbox[-1]["text"])

    def test_contact_sms_off_until_turned_on(self):
        self.contact_post()
        self.assertEqual(outbox, [])
        SmsTemplate.objects.filter(event="contact_new").update(active=True)
        self.contact_post()
        self.assertEqual(outbox[-1]["to"], ["09120000001"])


@override_settings(SMS_BACKEND=LOCMEM)
class AdminPageTests(TestCase):
    def setUp(self):
        outbox.clear()
        call_command("seed_content", stdout=open("/dev/null", "w"))
        self.admin = User.objects.create_superuser("admin", "a@example.org", "pw")
        self.client.force_login(self.admin)

    def test_page_and_test_send(self):
        self.assertContains(self.client.get("/admin/sms_admin/"), "ارسال پیامک خاموش است")
        response = self.client.post("/admin/sms_admin/", {"mobile": "09121234567", "text": "آزمایش"}, follow=True)
        self.assertContains(response, "تحویل شد")
        self.assertEqual(outbox[-1], {"to": ["09121234567"], "text": "آزمایش"})
        for url in ["/admin/snippets/sms/smstemplate/", "/admin/settings/sms/smssettings/"]:
            self.assertEqual(self.client.get(url, follow=True).status_code, 200, url)

    def test_staff_without_permission_cannot_open(self):
        user = User.objects.create_user("x", "x@example.org", "pw")
        user.user_permissions.add(*Permission.objects.filter(codename="access_admin"))
        self.client.force_login(user)
        self.assertNotEqual(self.client.get("/admin/sms_admin/").status_code, 200)
