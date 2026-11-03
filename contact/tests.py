import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from wagtail.contrib.forms.models import FormSubmission

from contact.models import Complaint
from core.models import SiteSettings

TMP_PRIVATE = tempfile.mkdtemp()


@override_settings(PRIVATE_MEDIA_ROOT=TMP_PRIVATE)
class ContactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=open("/dev/null", "w"))
        site_settings = SiteSettings.load()
        site_settings.notification_email = "secretariat@example.org"
        site_settings.save()

        User = get_user_model()
        cls.commissioner = User.objects.create_user("comm", email="comm@example.org", password="pw-12345-xyz")
        cls.commissioner.groups.add(Group.objects.get(name="کمیسیون نظارتی"))
        cls.secretary = User.objects.create_user("sec", email="sec@example.org", password="pw-12345-xyz")
        cls.secretary.groups.add(Group.objects.get(name="دبیرخانه"))

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_PRIVATE, ignore_errors=True)

    def test_pages_render(self):
        for url in ["/fa/contact/", "/en/contact/", "/fa/complaint/", "/en/complaint/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get("/en/contact/"), 'href="/en/complaint/"')

    def contact_post(self, url="/fa/contact/", **extra):
        response = self.client.get(url)
        form = response.context["form"]
        data = {}
        for name, field in form.fields.items():
            data[name] = "a@example.org" if field.__class__.__name__ == "EmailField" else "سلام"
        data.update(extra)
        return self.client.post(url, data)

    def test_contact_form_saves_and_emails_secretariat(self):
        response = self.contact_post()
        self.assertContains(response, "پیام شما به دبیرخانه رسید")
        self.assertEqual(FormSubmission.objects.count(), 1)
        self.assertEqual(mail.outbox[0].to, ["secretariat@example.org"])
        self.assertEqual(mail.outbox[0].reply_to, ["a@example.org"])

    def test_contact_honeypot(self):
        self.contact_post(website="http://spam")
        self.assertEqual(FormSubmission.objects.count(), 0)

    def complaint_data(self, **extra):
        data = {"relation": "buyer", "subject_of_complaint": "یک تولیدکننده", "category": "product",
                "description": "متن محرمانه شکایت"}
        data.update(extra)
        return data

    def test_complaint_saved_and_commission_notified_without_details(self):
        response = self.client.post("/fa/complaint/", self.complaint_data())
        complaint = Complaint.objects.get()
        self.assertContains(response, complaint.tracking_code)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["comm@example.org"])
        self.assertIn(complaint.tracking_code, mail.outbox[0].body)
        self.assertNotIn("متن محرمانه شکایت", mail.outbox[0].body)

    def test_complaint_requires_description(self):
        response = self.client.post("/en/complaint/", self.complaint_data(description=""))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertFalse(Complaint.objects.exists())

    def test_complaint_rejects_bad_attachment_type(self):
        bad = SimpleUploadedFile("x.exe", b"MZ", content_type="application/octet-stream")
        self.client.post("/fa/complaint/", self.complaint_data(attachment=bad))
        self.assertFalse(Complaint.objects.exists())

    def test_only_commission_sees_complaints_in_admin(self):
        complaint = Complaint.objects.create(subject_of_complaint="x", description="محرمانه")
        self.client.force_login(self.secretary)
        self.assertNotEqual(self.client.get("/admin/complaints/").status_code, 200)
        self.assertNotEqual(self.client.get(f"/admin/complaints/edit/{complaint.pk}/").status_code, 200)
        self.client.force_login(self.commissioner)
        self.assertContains(self.client.get("/admin/complaints/"), complaint.tracking_code)
        self.assertContains(self.client.get(f"/admin/complaints/edit/{complaint.pk}/"), "محرمانه")

    def test_attachment_download_only_for_commission(self):
        pdf = SimpleUploadedFile("evidence.pdf", b"%PDF-1.4", content_type="application/pdf")
        self.client.post("/fa/complaint/", self.complaint_data(attachment=pdf))
        complaint = Complaint.objects.get()
        self.assertTrue(complaint.attachment.path.startswith(TMP_PRIVATE))
        url = complaint.attachment_url()
        self.assertNotEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.secretary)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.commissioner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(complaint.tracking_code, response["Content-Disposition"])
        self.assertContains(self.client.get(f"/admin/complaints/edit/{complaint.pk}/"), url)
