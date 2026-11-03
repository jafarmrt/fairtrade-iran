import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from wagtail.models import Collection

from archive.models import ArchiveDocument

TMP_PRIVATE = tempfile.mkdtemp()


@override_settings(PRIVATE_MEDIA_ROOT=TMP_PRIVATE)
class DocumentsPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=open("/dev/null", "w"))

        def add(collection_name, title, title_en=""):
            doc = ArchiveDocument(title=title, title_en=title_en,
                                  collection=Collection.objects.get(name=collection_name))
            doc.file.save(f"{title_en or 'doc'}.pdf", ContentFile(b"%PDF-1.4 test"), save=True)
            return doc

        cls.public = add("اسناد عمومی", "اساسنامه", "Statutes")
        cls.public_fa_only = add("اسناد عمومی", "گزارش داخلی فارسی")
        cls.members = add("اسناد اعضا", "صورت‌جلسه مجمع", "Assembly minutes")
        cls.board = add("اسناد هیئت مدیره", "صورت‌جلسه هیئت مدیره", "Board minutes")

        User = get_user_model()
        cls.member = User.objects.create_user("member", password="pw-12345-xyz")
        cls.member.groups.add(Group.objects.get(name="اعضا"))

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_PRIVATE, ignore_errors=True)

    def test_files_are_stored_outside_public_media(self):
        self.assertTrue(self.public.file.path.startswith(TMP_PRIVATE))

    def test_public_documents_listed(self):
        response = self.client.get("/fa/documents/")
        self.assertContains(response, "اساسنامه")
        self.assertContains(response, "گزارش داخلی فارسی")

    def test_english_lists_only_documents_with_english_title(self):
        response = self.client.get("/en/documents/")
        self.assertContains(response, "Statutes")
        self.assertNotContains(response, "گزارش داخلی فارسی")

    def test_anonymous_sees_locked_member_section_and_no_board_section(self):
        response = self.client.get("/fa/documents/")
        self.assertContains(response, "این اسناد ویژه اعضاست")
        self.assertNotContains(response, "صورت‌جلسه مجمع")
        self.assertNotContains(response, "صورت‌جلسه هیئت مدیره")
        self.assertNotContains(response, "اسناد هیئت مدیره.")

    def test_member_sees_member_documents_but_not_board(self):
        self.client.force_login(self.member)
        response = self.client.get("/fa/documents/")
        self.assertContains(response, "صورت‌جلسه مجمع")
        self.assertNotContains(response, "صورت‌جلسه هیئت مدیره")

    def test_download_respects_collection_restriction(self):
        self.assertEqual(self.client.get(self.public.url).status_code, 200)
        self.assertNotEqual(self.client.get(self.members.url).status_code, 200)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.members.url).status_code, 200)
        self.assertNotEqual(self.client.get(self.board.url).status_code, 200)
