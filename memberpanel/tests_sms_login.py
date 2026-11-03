"""Sign-in with an SMS code, the sign-in mobile page, and the member's official identity fields."""

import re

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import override_settings

from members.models import Member
from sms import backends as sms_backends
from sms.models import SmsSettings

from .models import LoginMobile, PanelSettings
from .tests import PanelTestCase

MOBILE = "09121112233"


def last_code():
    return re.search(r"\d{6}", sms_backends.outbox[-1]["text"]).group(0)


@override_settings(SMS_BACKEND="sms.backends.LocmemBackend")
class SmsLoginTests(PanelTestCase):
    def setUp(self):
        cache.clear()
        sms_backends.outbox.clear()
        sms = SmsSettings.load()
        sms.enabled = True
        sms.save()
        panel = PanelSettings.load()
        panel.sms_login = True
        panel.save()
        LoginMobile.objects.create(user=self.user, mobile=MOBILE)

    def send(self, mobile=MOBILE, lang="fa"):
        return self.client.post(f"/{lang}/panel/login/sms/", {"step": "send", "mobile": mobile})

    def test_login_with_code(self):
        self.assertContains(self.client.get("/fa/panel/login/"), "ورود با کد پیامکی")
        self.send("۰۹۱۲ ۱۱۱ ۲۲۳۳")  # Persian digits and spaces
        self.assertEqual(sms_backends.outbox[-1]["to"], [MOBILE])
        page = self.client.get("/fa/panel/login/sms/")
        self.assertContains(page, "0912•••2233")
        response = self.client.post("/fa/panel/login/sms/", {"step": "verify", "code": last_code()})
        self.assertRedirects(response, "/fa/panel/", fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertIsNotNone(LoginMobile.objects.get(user=self.user).verified_at)

    def test_wrong_code_and_attempt_limit(self):
        self.send()
        code = last_code()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.client.post("/fa/panel/login/sms/", {"step": "verify", "code": wrong})
        response = self.client.post("/fa/panel/login/sms/", {"step": "verify", "code": code})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(response.status_code, 200)

    def test_unknown_number_gets_the_same_page_and_no_sms(self):
        response = self.send("09129998877")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(sms_backends.outbox, [])
        self.assertContains(self.client.get("/fa/panel/login/sms/"), "0912•••8877")
        self.client.post("/fa/panel/login/sms/", {"step": "verify", "code": "123456"})
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                           "LOCATION": "sms-login-tests"}})
    def test_sending_is_limited(self):
        cache.clear()
        for _ in range(8):
            self.client.post("/fa/panel/login/sms/", {"step": "restart"})
            self.send()
        self.assertLessEqual(len(sms_backends.outbox), 5)

    def test_inactive_user_cannot_sign_in(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.send()
        self.assertEqual(sms_backends.outbox, [])

    def test_off_when_disabled(self):
        panel = PanelSettings.load()
        panel.sms_login = False
        panel.save()
        self.assertNotContains(self.client.get("/fa/panel/login/"), "ورود با کد پیامکی")
        self.assertRedirects(self.client.get("/fa/panel/login/sms/"), "/fa/panel/login/",
                             fetch_redirect_response=False)

    def test_english_page(self):
        self.assertContains(self.client.get("/en/panel/login/sms/"), "Send code")
        response = self.send("0912", lang="en")
        self.assertContains(response, "11 digits")

    def test_member_sets_own_mobile(self):
        LoginMobile.objects.all().delete()
        self.login()
        self.assertContains(self.client.get("/fa/panel/mobile/"), "هنوز شماره موبایلی")
        self.client.post("/fa/panel/mobile/", {"step": "send", "mobile": "09125556677"})
        self.client.post("/fa/panel/mobile/", {"step": "verify", "code": last_code()})
        entry = LoginMobile.objects.get(user=self.user)
        self.assertEqual(entry.mobile, "09125556677")
        self.assertIsNotNone(entry.verified_at)
        # a number that belongs to someone else is refused
        other = User.objects.create_user("other", "other@example.org", "pw")
        LoginMobile.objects.create(user=other, mobile="09124443322")
        response = self.client.post("/fa/panel/mobile/", {"step": "send", "mobile": "09124443322"})
        self.assertContains(response, "حساب دیگری")


class IdentityFieldTests(PanelTestCase):
    def test_member_identity_is_validated(self):
        member = Member.objects.get(pk=self.member.pk)
        member.national_id = "۰۰۱۲۳۴۵۶۷۸"
        with self.assertRaises(ValidationError) as ctx:
            member.full_clean()
        self.assertIn("national_id", ctx.exception.message_dict)
        member.national_id = "0499370899"
        member.legal_id = "10100000000"
        with self.assertRaises(ValidationError) as ctx:
            member.full_clean()
        self.assertEqual(set(ctx.exception.message_dict), {"legal_id"})
        member.legal_id = ""
        member.economic_code = "۴۱۱ ۱۱۱"
        member.full_clean()
        self.assertEqual(member.economic_code, "411111")

    def test_identity_is_not_public(self):
        Member.objects.filter(pk=self.member.pk).update(national_id="0499370899", economic_code="411999888777")
        page = self.client.get(f"/fa/members/{self.member.slug}/")
        self.assertNotContains(page, "0499370899")
        self.assertNotContains(page, "411999888777")
