import datetime
import io
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings

from core.models import MembershipSettings
from members.models import Member
from membership.jalali import to_gregorian
from membership.models import Certificate, MembershipApplication, add_months

from . import daily
from .models import Decision, Dues, DuesPayment
from .services import (
    StandingError,
    decide,
    issue_by_hand,
    issue_due,
    period_for,
    review_payment,
    submit_receipt,
)

QUIET = io.StringIO()
PRIVATE = tempfile.mkdtemp()
D = datetime.date


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE, WAGTAILADMIN_BASE_URL="https://example.org")
class StandingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=QUIET)
        ms = MembershipSettings.load()
        ms.annual_fee_producer = 5_000_000
        ms.annual_fee_individual = 1_000_000
        ms.card_number = "6037-0000-0000-0000"
        ms.save()
        Member.objects.update(status=Member.OFFICIAL, joined_on=D(2025, 1, 1))
        cls.member = Member.objects.get(slug="armoz")
        cls.user = User.objects.create_user("maryam", "maryam@example.org", "pw-12345")
        cls.member.managers.add(cls.user)
        cls.secretary = User.objects.create_user("sec", "sec@example.org", "pw", is_staff=True)
        cls.secretary.groups.add(Group.objects.get(name="دبیرخانه"))
        cls.commissioner = User.objects.create_user("com", "com@example.org", "pw", is_staff=True)
        cls.commissioner.groups.add(Group.objects.get(name="کمیسیون نظارتی"))

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(PRIVATE, ignore_errors=True)

    def setUp(self):
        # Send e-mails queued with transaction.on_commit straight away (TestCase never commits).
        patcher = mock.patch("django.db.transaction.on_commit", side_effect=lambda func, *a, **k: func())
        patcher.start()
        self.addCleanup(patcher.stop)

    def fresh(self):
        self.member.refresh_from_db()
        return self.member

    def receipt(self):
        return SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 test", content_type="application/pdf")


class PeriodTests(StandingTestCase):
    def test_fixed_period_starts_on_farvardin_first(self):
        ms = MembershipSettings.load()
        self.assertEqual(period_for(self.member, D(2026, 11, 3), ms), (1405, D(2026, 3, 21)))
        # 30 days before Nowruz 1406 the next year is already within the issuing window.
        self.assertEqual(period_for(self.member, D(2027, 2, 25), ms, ahead_days=30), (1406, to_gregorian(1406, 1, 1)))

    def test_anniversary_period(self):
        ms = MembershipSettings.load()
        ms.dues_cycle = ms.DUES_ANNIVERSARY
        self.member.joined_on = D(2024, 6, 10)
        year, start = period_for(self.member, D(2026, 11, 3), ms)
        self.assertEqual(start, D(2026, 6, 10))

    def test_issue_in_window_only(self):
        # Mid-year after the deadline: nothing is billed automatically.
        self.assertEqual(issue_due(D(2026, 11, 3)), [])
        # Early in the window before Nowruz 1406: producers and individuals with a fee get dues.
        created = issue_due(D(2027, 3, 1))
        self.assertTrue(created)
        dues = Dues.objects.get(member=self.member)
        self.assertEqual((dues.year, dues.amount), (1406, 5_000_000))
        self.assertEqual(dues.due_date, to_gregorian(1406, 1, 1) + datetime.timedelta(days=30))
        # Types without a fee are skipped; running again creates nothing new.
        self.assertFalse(Dues.objects.filter(member__member_type="institution").exists())
        self.assertEqual(issue_due(D(2027, 3, 2)), [])
        self.assertIn("maryam@example.org", [m.to[0] for m in mail.outbox])

    def test_trial_and_new_members(self):
        Member.objects.filter(pk=self.member.pk).update(status=Member.TRIAL)
        issue_due(D(2027, 3, 1))
        self.assertFalse(Dues.objects.filter(member=self.member).exists())
        ms = MembershipSettings.load()
        ms.dues_for_trial = True
        ms.save()
        issue_due(D(2027, 3, 1))
        self.assertTrue(Dues.objects.filter(member=self.member).exists())

    def test_issue_by_hand_gives_full_payment_period(self):
        dues = issue_by_hand(self.member)
        self.assertGreater(dues.due_date, D.today())
        with self.assertRaises(StandingError):
            issue_by_hand(self.member)


class DailyTimelineTests(StandingTestCase):
    """Bill -> reminder -> warning -> 3 months -> suspension -> payment lifts it (section 1.7)."""

    def test_full_timeline(self):
        daily.run(D(2027, 3, 1))
        dues = Dues.objects.get(member=self.member)
        due = dues.due_date

        mail.outbox.clear()
        daily.run(due - datetime.timedelta(days=3))
        dues.refresh_from_db()
        self.assertIsNotNone(dues.reminded_on)
        self.assertTrue(any("یادآوری" in m.subject for m in mail.outbox))

        mail.outbox.clear()
        warn_day = due + datetime.timedelta(days=1)
        daily.run(warn_day)
        dues.refresh_from_db()
        self.assertEqual(dues.warned_on, warn_day)
        self.assertTrue(any("اخطار کتبی" in m.subject for m in mail.outbox))
        warning = self.member.decisions.get(kind=Decision.Kind.WARNING)
        self.assertEqual(warning.decided_by, Decision.Body.SYSTEM)
        # Running again on the same day sends nothing twice.
        n = len(mail.outbox)
        daily.run(warn_day)
        self.assertEqual(self.member.decisions.count(), 1)
        self.assertEqual(len([m for m in mail.outbox[n:] if "اخطار" in m.subject]), 0)

        # Two months later: still not suspended.
        daily.run(warn_day + datetime.timedelta(days=60))
        self.assertEqual(self.fresh().status, Member.OFFICIAL)
        # Three months after the warning: suspended, hidden from the site, products hidden.
        daily.run(add_months(warn_day, 3))
        member = self.fresh()
        self.assertEqual(member.status, Member.SUSPENDED)
        self.assertEqual(member.status_before_suspension, Member.OFFICIAL)
        self.assertFalse(Member.visible().filter(pk=member.pk).exists())
        self.assertNotIn(self.user, Group.objects.get(name="اعضا").user_set.all())

        # The member pays from the panel; the secretariat confirms; suspension lifted.
        payment = submit_receipt(Dues.objects.get(pk=dues.pk), self.user, 5_000_000, reference="123",
                                 receipt=self.receipt())
        review_payment(payment, self.secretary, confirm=True)
        member = self.fresh()
        self.assertEqual(member.status, Member.OFFICIAL)
        self.assertIsNone(member.suspended_until)
        self.assertTrue(member.decisions.filter(kind=Decision.Kind.LIFT, reason=Decision.Reason.PAID).exists())
        self.assertIn(self.user, Group.objects.get(name="اعضا").user_set.all())

    def test_manual_suspension_mode_only_reports(self):
        ms = MembershipSettings.load()
        ms.dues_auto_suspend = False
        ms.save()
        daily.run(D(2027, 3, 1))
        dues = Dues.objects.get(member=self.member)
        daily.run(dues.due_date + datetime.timedelta(days=1))
        mail.outbox.clear()
        daily.run(dues.due_date + datetime.timedelta(days=100))
        self.assertEqual(self.fresh().status, Member.OFFICIAL)
        self.assertTrue(any("sec@example.org" in m.to and "تصمیم بگیرید" in m.body for m in mail.outbox))

    def test_ended_suspension_reported(self):
        decide(self.member, Decision.Kind.SUSPEND, Decision.Reason.DUES, user=self.secretary, months=1)
        mail.outbox.clear()
        daily.run(self.fresh().suspended_until)
        self.assertTrue(any("رفع کنید یا عضویت را لغو کنید" in m.body for m in mail.outbox))


class DecisionTests(StandingTestCase):
    def test_roles(self):
        with self.assertRaises(StandingError):
            decide(self.member, Decision.Kind.SUSPEND, Decision.Reason.DUES, user=self.commissioner)
        with self.assertRaises(StandingError):
            decide(self.member, Decision.Kind.SUSPEND, Decision.Reason.AUDIT, user=self.secretary,
                   decision_reference="x")
        # The commission's suspension and cancellation votes are collective: minutes needed.
        with self.assertRaises(StandingError):
            decide(self.member, Decision.Kind.SUSPEND, Decision.Reason.AUDIT, user=self.commissioner)
        d = decide(self.member, Decision.Kind.SUSPEND, Decision.Reason.AUDIT, user=self.commissioner,
                   decision_reference="صورتجلسه ۱۲", months=12)
        # Capped at the maximum of six months.
        self.assertEqual(d.ends_on, add_months(D.today(), 6))

    def test_cancel_and_reinstate(self):
        application = MembershipApplication.objects.create(member_type="producer", name="آرموز",
                                                           email="a@example.org", phone="1", status="member")
        Certificate.objects.create(application=application, number="FTH-1405-0001", name="آرموز",
                                   member_type="producer")
        Member.objects.filter(pk=self.member.pk).update(application=application)
        member = self.fresh()
        d = decide(member, Decision.Kind.CANCEL, Decision.Reason.SERIOUS, user=self.commissioner,
                   decision_reference="صورتجلسه ۳", message="کار کودک")
        member = self.fresh()
        self.assertEqual(member.status, Member.CANCELLED)
        self.assertEqual(d.reapply_after, add_months(D.today(), 36))
        self.assertTrue(Certificate.objects.get(number="FTH-1405-0001").revoked)
        self.assertFalse(Member.visible().filter(pk=member.pk).exists())
        self.assertTrue(any("لغو عضویت" in m.subject for m in mail.outbox))
        decide(member, Decision.Kind.REINSTATE, Decision.Reason.APPEAL, user=self.secretary)
        member = self.fresh()
        self.assertEqual(member.status, Member.OFFICIAL)
        self.assertFalse(Certificate.objects.get(number="FTH-1405-0001").revoked)

    def test_wrong_status(self):
        with self.assertRaises(StandingError):
            decide(self.member, Decision.Kind.LIFT, Decision.Reason.RESOLVED, user=self.secretary)


class PanelTests(StandingTestCase):
    def test_member_sends_receipt(self):
        dues = issue_by_hand(self.member)
        self.client.force_login(self.user)
        response = self.client.get("/fa/panel/")
        self.assertContains(response, "پرداخت و ارسال رسید")
        url = f"/fa/panel/{self.member.pk}/membership/"
        response = self.client.get(url)
        self.assertContains(response, "6037-0000-0000-0000")
        mail.outbox.clear()
        response = self.client.post(url, {"dues": dues.pk, "amount": "5000000", "reference": "R1",
                                          "paid_on_text": "۱۴۰۵/۰۸/۱۲", "receipt": self.receipt()})
        self.assertRedirects(response, url, fetch_redirect_response=False)
        dues.refresh_from_db()
        self.assertEqual(dues.status, Dues.Status.PENDING)
        self.assertTrue(any("sec@example.org" in m.to for m in mail.outbox))
        payment = dues.payments.get()
        self.assertTrue(payment.receipt.path.startswith(PRIVATE))
        # English page works too.
        self.assertContains(self.client.get(f"/en/panel/{self.member.pk}/membership/"), "Annual membership fee")

    def test_other_members_page_is_hidden(self):
        other = Member.objects.exclude(pk=self.member.pk).first()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/fa/panel/{other.pk}/membership/").status_code, 404)

    def test_suspended_member_still_sees_page(self):
        decide(self.member, Decision.Kind.SUSPEND, Decision.Reason.DUES, user=self.secretary)
        self.client.force_login(self.user)
        response = self.client.get(f"/fa/panel/{self.member.pk}/membership/")
        self.assertContains(response, "تعلیق تا")
        self.assertEqual(self.client.get(f"/fa/panel/{self.member.pk}/profile/").status_code, 302)


class AdminTests(StandingTestCase):
    def test_staff_pages_and_actions(self):
        dues = issue_by_hand(self.member)
        payment = submit_receipt(dues, self.user, 5_000_000, receipt=self.receipt())
        self.client.force_login(self.secretary)
        self.assertContains(self.client.get("/admin/standing/?show=pending"), self.member.name)
        url = f"/admin/standing/member/{self.member.pk}/"
        self.assertContains(self.client.get(url), "تأیید پرداخت")
        response = self.client.get(f"/admin/standing/receipt/{payment.pk}/")
        self.assertEqual(response.status_code, 200)
        self.client.post(url, {"action": "reject", "dues": dues.pk, "payment": payment.pk, "message": "ناخوانا"})
        payment.refresh_from_db()
        self.assertEqual(payment.status, DuesPayment.Status.REJECTED)
        self.assertEqual(Dues.objects.get(pk=dues.pk).status, Dues.Status.UNPAID)
        self.client.post(url, {"action": "record", "dues": dues.pk, "amount": "5000000", "reference": "cash"})
        self.assertEqual(Dues.objects.get(pk=dues.pk).status, Dues.Status.PAID)
        self.client.post(url, {"action": "decision", "kind": "notice", "reason": "other", "message": "یادداشت"})
        self.assertTrue(self.member.decisions.filter(kind="notice").exists())
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_access(self):
        member_user = self.user
        self.client.force_login(member_user)
        self.assertNotEqual(self.client.get("/admin/standing/").status_code, 200)
        self.client.force_login(self.commissioner)
        self.assertEqual(self.client.get("/admin/standing/").status_code, 200)
        dues = issue_by_hand(self.member)
        # Only the secretariat handles dues.
        self.client.post(f"/admin/standing/member/{self.member.pk}/", {"action": "waive", "dues": dues.pk})
        self.assertEqual(Dues.objects.get(pk=dues.pk).status, Dues.Status.UNPAID)

    def test_command(self):
        out = io.StringIO()
        call_command("membership_standing", "--today", "2027-03-01", stdout=out)
        self.assertIn("Dues issued", out.getvalue())


@override_settings(SMS_BACKEND="sms.backends.LocmemBackend")
class SmsTests(StandingTestCase):
    def test_suspension_sms(self):
        from sms.backends import outbox
        from sms.tests import enable

        enable()
        outbox.clear()
        Member.objects.filter(pk=self.member.pk).update(public_phone="09121112233")
        decide(self.fresh(), Decision.Kind.SUSPEND, Decision.Reason.DUES, user=self.secretary)
        self.assertEqual(outbox[-1]["to"], ["09121112233"])
        self.assertIn("تعلیق", outbox[-1]["text"])
