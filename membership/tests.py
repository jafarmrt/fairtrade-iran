import datetime
import os
import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import MembershipSettings

from .jalali import format_jalali
from .models import (
    ApplicationDocument,
    ApplicationQuestion,
    Certificate,
    MembershipApplication,
    MembershipPage,
    Status,
    add_months,
)
from .workflow import WorkflowError, applicant_resubmit, perform

QUIET = open(os.devnull, "w")
TMP = tempfile.mkdtemp(prefix="ft-private-")


def pdf(name="doc.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")


@override_settings(PRIVATE_MEDIA_ROOT=TMP, WAGTAILADMIN_BASE_URL="https://example.org")
class MembershipTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=QUIET)
        ms = MembershipSettings.load()
        ms.application_fee_producer = 5_000_000
        ms.application_fee_individual = 1_000_000
        ms.card_number = "6037-0000-0000-0000"
        ms.save()

        cls.secretary = User.objects.create_user("sec", "sec@example.org", "pw")
        cls.secretary.groups.add(Group.objects.get(name="دبیرخانه"))
        cls.commissioner = User.objects.create_user("com", "com@example.org", "pw")
        cls.commissioner.groups.add(Group.objects.get(name="کمیسیون نظارتی"))
        cls.member = User.objects.create_user("mem", "mem@example.org", "pw")
        cls.member.groups.add(Group.objects.get(name="اعضا"))

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def producer_post(self, **extra):
        data = {
            "name": "کارگاه نمونه", "contact_person": "زهرا", "email": "app@example.org",
            "phone": "09120000000", "city": "کرمان", "agreed_principles": "on", "agreed_inspections": "on",
            "receipt": pdf("receipt.pdf"), "payment_reference": "123",
        }
        for q in ApplicationQuestion.for_type("producer"):
            if not q.required:
                continue
            key = f"q_{q.pk}"
            if q.field_type == "select":
                data[key] = q.choice_list()[0][0]
            elif q.field_type == "file":
                data[key] = pdf()
            else:
                data[key] = "پاسخ"
        data.update(extra)
        return data

    def submit_producer(self, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post("/fa/membership/apply/producer/", self.producer_post(**extra))
        self.assertEqual(response.status_code, 302, getattr(response, "context", {}) and response.context["form"].errors)
        return MembershipApplication.objects.latest("submitted_at")


class PublicPagesTests(MembershipTestCase):
    def test_pages_render_in_both_languages(self):
        for url in ["/fa/membership/", "/en/membership/", "/fa/membership/apply/producer/",
                    "/en/membership/apply/network/", "/fa/membership/track/", "/en/membership/certificate/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_page_shows_fees_and_deadlines_from_settings(self):
        response = self.client.get("/fa/membership/")
        self.assertContains(response, "۵٬۰۰۰٬۰۰۰")
        self.assertContains(response, "ظرف ۷ روز")
        ms = MembershipSettings.load()
        ms.secretariat_review_days = 10
        ms.save()
        self.assertContains(self.client.get("/en/membership/"), "Within 10 days")

    def test_language_switch_keeps_subpage(self):
        self.assertContains(self.client.get("/fa/membership/track/"), 'href="/en/membership/track/"')

    def test_unknown_type_is_404(self):
        self.assertEqual(self.client.get("/fa/membership/apply/other/").status_code, 404)

    def test_closed_applications(self):
        ms = MembershipSettings.load()
        ms.applications_open = False
        ms.save()
        response = self.client.get("/fa/membership/apply/producer/")
        self.assertNotContains(response, "ارسال درخواست")
        self.assertEqual(self.client.post("/fa/membership/apply/producer/", self.producer_post()).status_code, 200)
        self.assertFalse(MembershipApplication.objects.exists())

    def test_questions_are_editable(self):
        q = ApplicationQuestion.objects.create(label="پرسش تازه", label_en="A new question", for_individual=True,
                                               required=False)
        self.assertContains(self.client.get("/fa/membership/apply/individual/"), "پرسش تازه")
        self.assertContains(self.client.get("/en/membership/apply/individual/"), "A new question")
        self.assertNotContains(self.client.get("/fa/membership/apply/producer/"), "پرسش تازه")
        q.active = False
        q.save()
        self.assertNotContains(self.client.get("/fa/membership/apply/individual/"), "پرسش تازه")


class ApplicationFormTests(MembershipTestCase):
    def test_submit_creates_file_with_private_documents_and_emails(self):
        application = self.submit_producer()
        self.assertTrue(application.tracking_code.startswith("FT-"))
        self.assertEqual(application.status, Status.SUBMITTED)
        self.assertEqual(application.deadline, timezone.localdate() + datetime.timedelta(days=7))
        self.assertEqual(application.fee_amount, 5_000_000)
        self.assertTrue(application.agreed_inspections)
        self.assertTrue(any(a["value"] == "پاسخ" for a in application.answers))

        receipt = application.documents.get(kind=ApplicationDocument.Kind.RECEIPT)
        self.assertTrue(receipt.file.path.startswith(os.path.abspath(TMP)))
        self.assertNotIn("receipt", os.path.basename(receipt.file.name))  # random name on disk

        recipients = [m.to for m in mail.outbox]
        self.assertIn(["app@example.org"], recipients)
        self.assertIn(["sec@example.org"], recipients)
        self.assertIn(application.tracking_code, mail.outbox[0].body)

        done = self.client.get("/fa/membership/apply-done/")
        self.assertContains(done, application.tracking_code)

    def test_producer_must_accept_inspections(self):
        data = self.producer_post()
        del data["agreed_inspections"]
        response = self.client.post("/fa/membership/apply/producer/", data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MembershipApplication.objects.exists())

    def test_disallowed_file_type_is_rejected(self):
        data = self.producer_post(receipt=SimpleUploadedFile("x.exe", b"MZ"))
        self.assertEqual(self.client.post("/fa/membership/apply/producer/", data).status_code, 200)
        self.assertFalse(MembershipApplication.objects.exists())

    def test_honeypot_blocks_bots(self):
        self.client.post("/fa/membership/apply/producer/", self.producer_post(nickname="bot"))
        self.assertFalse(MembershipApplication.objects.exists())

    def test_english_form_keeps_language_and_names(self):
        data = {"name": "Jane Doe", "name_en": "جین", "email": "jane@example.org", "phone": "+44 7700 900123",
                "city": "London", "agreed_principles": "on", "receipt": pdf()}
        for q in ApplicationQuestion.for_type("individual"):
            if q.required:
                data[f"q_{q.pk}"] = "answer"
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post("/en/membership/apply/individual/", data)
        self.assertEqual(response.status_code, 302)
        application = MembershipApplication.objects.get()
        self.assertEqual((application.language, application.name, application.name_en), ("en", "جین", "Jane Doe"))
        self.assertIn("We received your membership application", mail.outbox[0].subject)


class WorkflowTests(MembershipTestCase):
    def test_full_process_to_certificate(self):
        application = self.submit_producer()
        mail.outbox.clear()

        with self.assertRaisesMessage(WorkflowError, "هزینه"):
            perform(application, "to_commission", self.secretary)
        with self.assertRaises(WorkflowError):  # the commission cannot do the secretariat's job
            perform(application, "confirm_fee", self.commissioner)
        perform(application, "confirm_fee", self.secretary)
        with self.captureOnCommitCallbacks(execute=True):
            perform(application, "to_commission", self.secretary)
        self.assertEqual(application.status, Status.COMMISSION)
        self.assertEqual(application.deadline, timezone.localdate() + datetime.timedelta(days=30))
        self.assertIn(["com@example.org"], [m.to for m in mail.outbox])

        with self.assertRaises(WorkflowError):  # the secretariat cannot vote
            perform(application, "accept_trial", self.secretary)
        with self.assertRaisesMessage(WorkflowError, "بازدید میدانی"):
            perform(application, "accept_trial", self.commissioner)
        perform(application, "record_visit", self.commissioner, field_visit_date=timezone.localdate())
        perform(application, "accept_trial", self.commissioner, decision_reference="صورتجلسه ۵")
        self.assertEqual(application.status, Status.TRIAL)
        self.assertEqual(application.trial_ends_on, add_months(timezone.localdate(), 3))

        perform(application, "extend_trial", self.commissioner)
        self.assertEqual(application.trial_ends_on, add_months(timezone.localdate(), 6))
        with self.assertRaises(WorkflowError):  # extension is one-off
            perform(application, "extend_trial", self.commissioner)

        perform(application, "make_member", self.commissioner)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            perform(application, "register", self.secretary)
        self.assertEqual(application.status, Status.MEMBER)
        certificate = Certificate.objects.get(application=application)
        self.assertRegex(certificate.number, r"^FTH-14\d\d-0001$")
        self.assertIn(certificate.number, mail.outbox[0].body)

        response = self.client.get(f"/fa/membership/certificate/?number={certificate.number}")
        self.assertContains(response, "این گواهی معتبر است")
        self.assertContains(response, "کارگاه نمونه")
        certificate.revoked = True
        certificate.save()
        self.assertContains(self.client.get(f"/en/membership/certificate/?number={certificate.number}"),
                            "revoked")
        self.assertContains(self.client.get("/fa/membership/certificate/?number=NOPE"), "پیدا نشد")

    def test_reject_needs_reason(self):
        application = self.submit_producer()
        perform(application, "confirm_fee", self.secretary)
        perform(application, "to_commission", self.secretary)
        with self.assertRaises(WorkflowError):
            perform(application, "reject", self.commissioner, message="  ")
        perform(application, "reject", self.commissioner, message="فعالیت مستند نیست")
        self.assertTrue(application.is_closed)
        self.assertIsNone(application.deadline)

    def test_applicant_answers_incomplete_from_tracking_page(self):
        application = self.submit_producer()
        perform(application, "incomplete", self.secretary, message="مجوز را بفرستید")
        response = self.client.post("/fa/membership/track/", {
            "step": "lookup", "code": application.tracking_code.lower(), "email": "APP@example.org"})
        self.assertEqual(response.status_code, 302)
        page = self.client.get("/fa/membership/track/")
        self.assertContains(page, "مجوز را بفرستید")
        self.assertContains(page, "ارسال پاسخ و مدارک")

        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post("/fa/membership/track/", {
                "step": "resubmit", "message": "فرستادم", "documents": [pdf("a.pdf"), pdf("b.pdf")]})
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, Status.SUBMITTED)
        self.assertEqual(application.documents.filter(kind="additional").count(), 2)
        self.assertIn(["sec@example.org"], [m.to for m in mail.outbox])

    def test_wrong_email_does_not_reveal_file(self):
        application = self.submit_producer()
        response = self.client.post("/fa/membership/track/", {
            "step": "lookup", "code": application.tracking_code, "email": "other@example.org"})
        self.assertContains(response, "پیدا نشد")
        self.assertNotContains(response, "کارگاه نمونه")

    def test_resubmit_only_when_waiting(self):
        application = self.submit_producer()
        with self.assertRaises(WorkflowError):
            applicant_resubmit(application, "")

    def test_reminders(self):
        application = self.submit_producer()
        MembershipApplication.objects.filter(pk=application.pk).update(
            deadline=timezone.localdate() - datetime.timedelta(days=1))
        mail.outbox.clear()
        call_command("membership_reminders", stdout=QUIET)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("sec@example.org", mail.outbox[0].to)
        self.assertIn("گذشته از مهلت", mail.outbox[0].body)


class AdminTests(MembershipTestCase):
    def test_private_download_is_staff_only(self):
        application = self.submit_producer()
        document = application.documents.first()
        url = reverse("membership_applications:download", args=[document.pk])
        self.assertEqual(self.client.get(url).status_code, 302)  # anonymous: login
        self.client.force_login(self.member)
        self.assertIn(self.client.get(url).status_code, (302, 403))
        self.client.force_login(self.secretary)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 test")

    def test_secretariat_sees_list_and_acts(self):
        application = self.submit_producer()
        self.client.force_login(self.secretary)
        self.assertContains(self.client.get("/admin/"), "پرونده‌های عضویت نیازمند اقدام شما")
        index = self.client.get(reverse("membership_applications:index"))
        self.assertContains(index, application.tracking_code)
        detail_url = reverse("membership_applications:detail", args=[application.pk])
        detail = self.client.get(detail_url)
        self.assertContains(detail, "تأیید دریافت هزینه درخواست")
        self.assertNotContains(detail, "رأی: پذیرش آزمایشی")
        self.client.post(detail_url, {"action": "confirm_fee"})
        response = self.client.post(detail_url, {"action": "to_commission", "internal_note": "کامل"})
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, Status.COMMISSION)

    def test_commission_dashboard_lists_its_files(self):
        application = self.submit_producer()
        perform(application, "confirm_fee", self.secretary)
        perform(application, "to_commission", self.secretary)
        self.client.force_login(self.commissioner)
        self.assertContains(self.client.get("/admin/"), application.tracking_code)
        self.assertContains(self.client.get(reverse("membership_applications:detail", args=[application.pk])),
                            "ثبت بازدید میدانی")

    def test_certificate_print(self):
        application = self.submit_producer()
        from .workflow import issue_certificate

        certificate = issue_certificate(application)
        self.client.force_login(self.secretary)
        url = reverse("membership_applications:certificate_print", args=[certificate.pk])
        response = self.client.get(url)
        self.assertContains(response, "گواهی عضویت")
        self.assertContains(response, "کارگاه نمونه")
        self.assertContains(self.client.get(url + "?lang=en"), "Certificate of Membership")


class HelperTests(TestCase):
    def test_jalali(self):
        self.assertEqual(format_jalali(datetime.date(2026, 11, 2)), "۱۱ آبان ۱۴۰۵")
        self.assertEqual(format_jalali(datetime.date(2025, 3, 21), long=False), "۱۴۰۴/۰۱/۰۱")

    def test_add_months_clamps_day(self):
        self.assertEqual(add_months(datetime.date(2026, 11, 30), 3), datetime.date(2027, 2, 28))

    def test_one_page_per_locale(self):
        self.assertEqual(MembershipPage.objects.count(), 0)
