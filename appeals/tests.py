import datetime
import io
import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from contact.models import Complaint
from members.models import Member
from membership.jalali import format_jalali, parse_date
from membership.models import ApplicationEvent, Certificate, MembershipApplication, Status

from .models import Appeal, AppealSettings

QUIET = io.StringIO()
PRIVATE = tempfile.mkdtemp()


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE, WAGTAILADMIN_BASE_URL="https://example.org")
class CaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=QUIET)
        cls.member = Member.objects.get(slug="armoz")
        cls.user = User.objects.create_user("maryam", "maryam@example.org", "pw-12345", first_name="مریم")
        cls.member.managers.add(cls.user)
        cls.other = Member.objects.exclude(pk=cls.member.pk).first()
        cls.secretary = User.objects.create_user("dabir", "dabir@example.org", "pw-12345", is_staff=True)
        cls.secretary.groups.add(Group.objects.get(name="دبیر مجمع"))
        cls.commissioner = User.objects.create_user("komision", "kom@example.org", "pw-12345")
        cls.commissioner.groups.add(Group.objects.get(name="کمیسیون نظارتی"))

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(PRIVATE, ignore_errors=True)

    def setUp(self):
        self.client.force_login(self.user)

    def appeal_data(self, **extra):
        data = {"decision": "suspension", "decision_body": "secretariat",
                "decision_date": format_jalali(timezone.localdate() - datetime.timedelta(days=3), long=False),
                "decision_reference": "", "grounds": "حق عضویت را پرداخته بودیم.",
                "email": "maryam@example.org", "phone": ""}
        data.update(extra)
        return data


class JalaliParseTests(TestCase):
    def test_formats(self):
        self.assertEqual(parse_date("۱۴۰۵/۰۸/۱۲"), datetime.date(2026, 11, 3))
        self.assertEqual(parse_date("1405-8-12"), datetime.date(2026, 11, 3))
        self.assertEqual(parse_date("2026-11-03"), datetime.date(2026, 11, 3))
        self.assertIsNone(parse_date("1405/13/01"))
        self.assertIsNone(parse_date("دیروز"))


class MembershipFileTests(CaseTestCase):
    def make_application(self):
        application = MembershipApplication.objects.create(
            member_type="producer", name=self.member.name, email="maryam@example.org", phone="0912",
            status=Status.MEMBER,
        )
        self.member.application = application
        self.member.save()
        return application

    def test_file_shows_status_and_certificate(self):
        application = self.make_application()
        Certificate.objects.create(application=application, number="FT-1405-0001", name=self.member.name,
                                   member_type="producer")
        for lang in ("fa", "en"):
            response = self.client.get(f"/{lang}/panel/{self.member.pk}/membership/")
            self.assertContains(response, application.tracking_code)
            self.assertContains(response, "FT-1405-0001")
            self.assertContains(response, f"/panel/{self.member.pk}/certificate/")
        response = self.client.get(f"/en/panel/{self.member.pk}/certificate/")
        self.assertContains(response, "FT-1405-0001")

    def test_revoked_certificate_cannot_be_printed(self):
        application = self.make_application()
        Certificate.objects.create(application=application, number="FT-1405-0002", name=self.member.name,
                                   member_type="producer", revoked=True)
        self.assertEqual(self.client.get(f"/fa/panel/{self.member.pk}/certificate/").status_code, 404)

    def test_recent_rejection_offers_appeal(self):
        application = self.make_application()
        ApplicationEvent.objects.create(application=application, action="x", to_status=Status.NOT_ACCEPTED,
                                        message="دوره آزمایشی موفق نبود.")
        response = self.client.get(f"/fa/panel/{self.member.pk}/membership/")
        self.assertContains(response, "?decision=rejection")

    def test_other_members_file_is_hidden(self):
        self.assertEqual(self.client.get(f"/fa/panel/{self.other.pk}/membership/").status_code, 404)
        self.assertEqual(self.client.get(f"/fa/panel/{self.other.pk}/certificate/").status_code, 404)

    def test_file_without_application(self):
        self.assertEqual(self.client.get(f"/en/panel/{self.member.pk}/membership/").status_code, 200)


class ComplaintTests(CaseTestCase):
    def test_member_files_complaint(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f"/fa/panel/{self.member.pk}/complaints/", {
                "subject_of_complaint": "یک خریدار", "category": "payment", "description": "پول را نداد.",
            })
        self.assertRedirects(response, f"/fa/panel/{self.member.pk}/complaints/", fetch_redirect_response=False)
        complaint = Complaint.objects.get()
        self.assertEqual(complaint.member, self.member)
        self.assertEqual(complaint.submitted_by, self.user)
        self.assertEqual(complaint.email, "maryam@example.org")
        self.assertEqual(complaint.relation, "member")
        self.assertEqual(mail.outbox[-1].to, ["kom@example.org"])
        self.assertNotIn("پول را نداد", mail.outbox[-1].body)

    def test_member_sees_status_and_answer_only_for_own(self):
        mine = Complaint.objects.create(member=self.member, submitted_by=self.user, subject_of_complaint="الف",
                                        description="x", status="resolved", response="پیگیری شد و حل شد.",
                                        commission_notes="یادداشت محرمانه")
        Complaint.objects.create(subject_of_complaint="شکایت دیگران", description="y")
        for lang in ("fa", "en"):
            response = self.client.get(f"/{lang}/panel/{self.member.pk}/complaints/")
            self.assertContains(response, mine.tracking_code)
            self.assertContains(response, "پیگیری شد و حل شد.")
            self.assertNotContains(response, "یادداشت محرمانه")
            self.assertNotContains(response, "شکایت دیگران")

    def test_suspended_member_can_still_complain(self):
        Member.objects.filter(pk=self.member.pk).update(status=Member.SUSPENDED)
        self.assertEqual(self.client.get(f"/fa/panel/{self.member.pk}/complaints/").status_code, 200)


class AppealTests(CaseTestCase):
    def test_file_appeal(self):
        attachment = SimpleUploadedFile("letter.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f"/fa/panel/{self.member.pk}/appeals/new/",
                                        self.appeal_data(attachment=attachment))
        self.assertRedirects(response, f"/fa/panel/{self.member.pk}/appeals/", fetch_redirect_response=False)
        appeal = Appeal.objects.get()
        self.assertEqual(appeal.member, self.member)
        self.assertEqual(appeal.decision_date, timezone.localdate() - datetime.timedelta(days=3))
        self.assertEqual(appeal.decide_by, timezone.localdate() + datetime.timedelta(days=30))
        self.assertTrue(appeal.tracking_code.startswith("AP-"))
        recipients = {tuple(m.to) for m in mail.outbox}
        self.assertIn(("maryam@example.org",), recipients)
        self.assertIn(("dabir@example.org",), recipients)
        self.assertNotIn("حق عضویت را پرداخته", mail.outbox[-1].body)
        # The member and the secretary can download the attachment; others cannot.
        self.assertEqual(self.client.get(appeal.attachment_url()).status_code, 200)
        self.client.force_login(self.secretary)
        self.assertEqual(self.client.get(appeal.attachment_url()).status_code, 200)
        self.client.force_login(self.commissioner)
        self.assertEqual(self.client.get(appeal.attachment_url()).status_code, 403)

    def test_window_is_enforced(self):
        late = format_jalali(timezone.localdate() - datetime.timedelta(days=31), long=False)
        response = self.client.post(f"/fa/panel/{self.member.pk}/appeals/new/", self.appeal_data(decision_date=late))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مهلت ۳۰ روزه".replace("۳۰", "30"))
        self.assertFalse(Appeal.objects.exists())
        future = (timezone.localdate() + datetime.timedelta(days=2)).isoformat()
        response = self.client.post(f"/en/panel/{self.member.pk}/appeals/new/", self.appeal_data(decision_date=future))
        self.assertContains(response, "cannot be in the future")

    def test_window_is_editable(self):
        from core.models import MembershipSettings

        settings = MembershipSettings.load()
        settings.appeal_days = 60
        settings.save()
        late = (timezone.localdate() - datetime.timedelta(days=45)).isoformat()
        self.client.post(f"/en/panel/{self.member.pk}/appeals/new/", self.appeal_data(decision_date=late))
        self.assertEqual(Appeal.objects.get().language, "en")

    def test_suspended_member_can_appeal(self):
        Member.objects.filter(pk=self.member.pk).update(status=Member.SUSPENDED)
        self.client.post(f"/fa/panel/{self.member.pk}/appeals/new/", self.appeal_data())
        self.assertTrue(Appeal.objects.exists())

    def test_cannot_appeal_for_other_member(self):
        response = self.client.post(f"/fa/panel/{self.other.pk}/appeals/new/", self.appeal_data())
        self.assertEqual(response.status_code, 404)

    def test_prefill_from_query(self):
        response = self.client.get(f"/fa/panel/{self.member.pk}/appeals/new/?decision=rejection&date=2026-11-01")
        self.assertContains(response, 'value="rejection" selected')
        self.assertContains(response, "۱۴۰۵/۰۸/۱۰")

    def test_appeal_a_recorded_decision(self):
        from standing.models import Decision

        decision = Decision.objects.create(
            member=self.member, kind="suspend", reason="dues", decided_by="secretariat",
            decided_on=timezone.localdate() - datetime.timedelta(days=2),
            appeal_until=timezone.localdate() + datetime.timedelta(days=28), message="تعلیق برای بدهی")
        page = self.client.get(f"/fa/panel/{self.member.pk}/membership/")
        self.assertContains(page, f"?ref={decision.pk}")
        form = self.client.get(f"/fa/panel/{self.member.pk}/appeals/new/?ref={decision.pk}")
        self.assertContains(form, 'value="suspension" selected')
        self.assertContains(form, 'value="secretariat" selected')
        data = self.appeal_data(ref=str(decision.pk))
        self.client.post(f"/fa/panel/{self.member.pk}/appeals/new/", data)
        self.assertEqual(Appeal.objects.get().standing_decision, decision)
        self.assertNotContains(self.client.get(f"/fa/panel/{self.member.pk}/membership/"), f"?ref={decision.pk}")

    def test_recorded_decision_past_its_window_cannot_be_appealed(self):
        from standing.models import Decision

        decision = Decision.objects.create(
            member=self.member, kind="suspend", reason="dues", decided_by="secretariat",
            decided_on=timezone.localdate() - datetime.timedelta(days=90),
            appeal_until=timezone.localdate() - datetime.timedelta(days=60), message="تعلیق برای بدهی")
        url = f"/fa/panel/{self.member.pk}/appeals/new/"
        # Typing today's date does not reopen the window of a decision recorded 90 days ago.
        data = self.appeal_data(ref=str(decision.pk), decision_date="")
        data["decision_date"] = timezone.localdate().isoformat()
        response = self.client.post(url, data)
        self.assertRedirects(response, f"/fa/panel/{self.member.pk}/appeals/", fetch_redirect_response=False)
        self.assertFalse(Appeal.objects.exists())

    def test_ruling_needs_reasons_and_emails_member(self):
        self.client.post(f"/fa/panel/{self.member.pk}/appeals/new/", self.appeal_data())
        appeal = Appeal.objects.get()
        self.client.force_login(self.secretary)
        url = f"/admin/appeals/edit/{appeal.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        data = {"status": "overturned", "decide_by": appeal.decide_by.isoformat(), "hearing_date": "",
                "ruling": "", "secretary_notes": ""}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)  # form error: an overturn needs reasons
        appeal.refresh_from_db()
        self.assertEqual(appeal.status, "received")
        mail.outbox.clear()
        data["ruling"] = "رسید پرداخت پیش از تعلیق صادر شده بود؛ تعلیق نقض می‌شود."
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        appeal.refresh_from_db()
        self.assertEqual(appeal.status, "overturned")
        self.assertEqual(appeal.ruled_on, timezone.localdate())
        self.assertEqual(mail.outbox[0].to, ["maryam@example.org"])
        self.assertIn("تعلیق نقض می‌شود", mail.outbox[0].body)
        self.client.force_login(self.user)
        response = self.client.get(f"/fa/panel/{self.member.pk}/appeals/")
        self.assertContains(response, "تعلیق نقض می‌شود")
        self.assertContains(response, "رأی دبیر مجمع (قطعی)")

    def test_only_secretary_sees_appeals_in_admin(self):
        self.client.post(f"/fa/panel/{self.member.pk}/appeals/new/", self.appeal_data())
        board = User.objects.create_user("board", "b@example.org", "pw", is_staff=True)
        board.groups.add(Group.objects.get(name="هیئت مدیره"))
        self.client.force_login(board)
        self.assertNotEqual(self.client.get("/admin/appeals/").status_code, 200)
        self.client.force_login(self.secretary)
        self.assertEqual(self.client.get("/admin/appeals/").status_code, 200)

    def test_pages_render_in_both_languages(self):
        for lang in ("fa", "en"):
            self.assertEqual(self.client.get(f"/{lang}/panel/{self.member.pk}/appeals/").status_code, 200)
            self.assertEqual(self.client.get(f"/{lang}/panel/{self.member.pk}/appeals/new/").status_code, 200)
            self.assertContains(self.client.get(f"/{lang}/panel/"), f"/panel/{self.member.pk}/appeals/")


class ApplicantAppealTests(CaseTestCase):
    """Applicants rejected before the trial period appeal from the tracking page."""

    def setUp(self):
        self.client.logout()
        self.application = MembershipApplication.objects.create(
            member_type="producer", name="کارگاه نمونه", email="app@example.org", phone="0912",
            status=Status.REJECTED,
        )
        ApplicationEvent.objects.create(application=self.application, action="reject", to_status=Status.REJECTED,
                                        message="مدارک بازدید میدانی کافی نبود.",
                                        created_at=timezone.now() - datetime.timedelta(days=5))

    def lookup(self, lang="fa"):
        self.client.post(f"/{lang}/membership/track/", {
            "step": "lookup", "code": self.application.tracking_code, "email": "app@example.org"})

    def test_rejected_applicant_can_appeal(self):
        self.lookup()
        page = self.client.get("/fa/membership/track/")
        self.assertContains(page, 'name="step" value="appeal"')
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post("/fa/membership/track/", {"step": "appeal", "grounds": "بازدید انجام نشد.",
                                                                  "phone": ""})
        self.assertRedirects(response, "/fa/membership/track/?appealed=1", fetch_redirect_response=False)
        appeal = Appeal.objects.get()
        self.assertEqual(appeal.application, self.application)
        self.assertIsNone(appeal.member)
        self.assertEqual(appeal.decision, "rejection")
        self.assertEqual(appeal.email, "app@example.org")
        self.assertEqual(appeal.decision_date, timezone.localdate() - datetime.timedelta(days=5))
        recipients = {tuple(m.to) for m in mail.outbox}
        self.assertIn(("app@example.org",), recipients)
        self.assertIn(("dabir@example.org",), recipients)
        self.assertIn("/fa/membership/track/", [m for m in mail.outbox if m.to == ["app@example.org"]][0].body)
        # One appeal per decision; the page now shows its status instead of the form.
        page = self.client.get("/fa/membership/track/")
        self.assertContains(page, appeal.tracking_code)
        self.assertNotContains(page, 'name="step" value="appeal"')

    def test_no_appeal_after_window(self):
        self.application.events.update(created_at=timezone.now() - datetime.timedelta(days=40))
        self.lookup("en")
        page = self.client.get("/en/membership/track/")
        self.assertNotContains(page, 'name="step" value="appeal"')
        self.client.post("/en/membership/track/", {"step": "appeal", "grounds": "late"})
        self.assertFalse(Appeal.objects.exists())

    def test_no_appeal_while_in_progress(self):
        MembershipApplication.objects.filter(pk=self.application.pk).update(status=Status.COMMISSION)
        self.lookup()
        self.assertNotContains(self.client.get("/fa/membership/track/"), 'name="step" value="appeal"')

    def test_members_with_a_profile_appeal_from_the_panel(self):
        MembershipApplication.objects.filter(pk=self.application.pk).update(status=Status.NOT_ACCEPTED)
        self.member.application = self.application
        self.member.save()
        self.lookup()
        self.assertNotContains(self.client.get("/fa/membership/track/"), 'name="step" value="appeal"')
