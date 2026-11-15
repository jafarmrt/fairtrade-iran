"""The bilingual content package (content/) and its import (seed_content, import_content, admin page)."""

import io
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from home.content_import import find_phrases
from home.content_package import DEFAULT_DIR, ContentPackage, PackageError
from members.models import Member
from membership.models import ApplicationQuestion
from pages.models import PrinciplesPage, StandardPage

FOUNDATION = "بنیاد توسعه کارآفرینی زنان و جوانان"


def quiet(*args, **kwargs):
    out = io.StringIO()
    call_command(*args, stdout=out, **kwargs)
    return out.getvalue()


class PackageTests(TestCase):
    def test_bundled_package_is_valid_and_complete(self):
        pkg = ContentPackage()
        keys = {p["key"] for p in pkg.pages}
        self.assertTrue({"home", "about", "fair-trade", "principles", "members", "shop", "membership", "news",
                         "documents", "contact", "complaint", "wholesale", "privacy", "terms", "returns"} <= keys)
        for spec in pkg.pages:
            with self.subTest(page=spec["key"]):
                self.assertTrue(spec["fa"]["title"] and spec["en"]["title"])
        for q in pkg.questions:
            with self.subTest(question=q["label"]):
                self.assertTrue(q.get("label_en"), "every question has an English label")
                self.assertEqual(len(q.get("choices", [])), len(q.get("choices_en", [])))

    def test_former_founder_not_in_package_texts(self):
        for path in DEFAULT_DIR.rglob("*.yaml"):
            if path.name in ("checks.yaml", "members.yaml"):
                continue  # these name it on purpose, to remove it
            with self.subTest(file=path.name):
                text = path.read_text(encoding="utf-8")
                for phrase in ContentPackage().checks["forbidden_phrases"]:
                    self.assertNotIn(phrase, text)

    def test_bad_package_is_refused_with_a_clear_message(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copytree(DEFAULT_DIR, tmp / "content")
        (tmp / "content" / "pages" / "999-orphan.yaml").write_text(
            "key: orphan\ntype: pages.StandardPage\nparent: nowhere\nfa: {title: x, slug: x}\nen: {title: x, slug: x}\n",
            encoding="utf-8")
        with self.assertRaises(PackageError) as ctx:
            ContentPackage(tmp / "content")
        self.assertIn("nowhere", str(ctx.exception))


class FreshInstallTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        quiet("seed_content")

    def test_pages_in_both_languages(self):
        for url in ("/fa/", "/en/", "/fa/about/", "/en/about/", "/fa/fair-trade/", "/en/fair-trade/",
                    "/fa/principles/", "/en/principles/", "/fa/members/", "/en/members/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get("/en/fair-trade/"), "World Fair Trade Organization")
        self.assertContains(self.client.get("/fa/principles/"), "نمونه عملی")

    def test_founders(self):
        founders = Member.objects.filter(is_founding=True)
        self.assertEqual(founders.count(), 8)
        self.assertFalse(founders.filter(name__contains="کارآفرینی").exists())
        self.assertEqual(Member.objects.get(slug="armoz").name_en, "Ormuz")
        self.assertIn("Haftdast House", self.client.get("/en/members/").content.decode())

    def test_no_forbidden_phrase_anywhere(self):
        self.assertEqual(find_phrases(ContentPackage().checks["forbidden_phrases"]), [])

    def test_home_button_links_to_about(self):
        self.assertContains(self.client.get("/fa/"), 'href="/fa/about/"')

    def test_membership_questions(self):
        self.assertEqual(ApplicationQuestion.objects.count(), len(ContentPackage().questions))
        self.assertTrue(ApplicationQuestion.objects.filter(label__startswith="آیا کودک زیر ۱۵", for_producer=True).exists())

    def test_seed_again_and_update_change_nothing(self):
        out = quiet("seed_content")
        self.assertNotIn("created:", out)
        out = quiet("import_content", "--update")
        self.assertIn("nothing to change", out)


class OldSiteTests(TestCase):
    """A site seeded before the package: the Foundation is a founder and the About page names it."""

    @classmethod
    def setUpTestData(cls):
        quiet("seed_content")
        Member.objects.create(slug="women-youth-entrepreneurship-foundation", name=FOUNDATION,
                              name_en="Women and Youth Entrepreneurship Development Foundation",
                              member_type=Member.INSTITUTION, status=Member.OFFICIAL, is_founding=True,
                              is_featured=True)
        about = StandardPage.objects.get(slug="about", locale__language_code="fa")
        about.intro = f"هفت گروه تولیدی و {FOUNDATION}"
        about.save_revision().publish()

    def test_check_lists_the_places(self):
        out = quiet("import_content", "--check")
        self.assertIn("/about/", out)

    def test_dry_run_saves_nothing(self):
        out = quiet("import_content", "--update", "--dry-run")
        self.assertIn("Dry run", out)
        self.assertTrue(Member.objects.get(slug="women-youth-entrepreneurship-foundation").is_founding)
        self.assertIn(FOUNDATION, StandardPage.objects.get(slug="about", locale__language_code="fa").intro)

    def test_plain_import_withdraws_founder_but_keeps_page_edits(self):
        quiet("import_content")
        foundation = Member.objects.get(slug="women-youth-entrepreneurship-foundation")
        self.assertFalse(foundation.is_founding or foundation.is_featured or foundation.is_published)
        self.assertIn(FOUNDATION, StandardPage.objects.get(slug="about", locale__language_code="fa").intro)

    def test_update_replaces_texts(self):
        Member.objects.filter(slug="armoz").update(name_en="Armoz")
        quiet("import_content", "--update")
        about = StandardPage.objects.get(slug="about", locale__language_code="fa")
        self.assertNotIn(FOUNDATION, about.intro)
        self.assertGreaterEqual(about.revisions.count(), 3, "the edit stays in the page history")
        self.assertEqual(Member.objects.get(slug="armoz").name_en, "Ormuz")
        self.assertEqual(find_phrases(ContentPackage().checks["forbidden_phrases"]), [])
        self.assertNotContains(self.client.get("/fa/members/"), FOUNDATION)

    def test_new_page_goes_to_its_place_in_the_menu(self):
        StandardPage.objects.filter(slug="fair-trade", locale__language_code="en").delete()
        StandardPage.objects.filter(slug="fair-trade", locale__language_code="fa").delete()
        quiet("import_content")
        for lang in ("fa", "en"):
            page = StandardPage.objects.get(slug="fair-trade", locale__language_code=lang)
            self.assertEqual(page.get_prev_sibling().slug, "about")

    def test_update_restores_principles(self):
        page = PrinciplesPage.objects.get(locale__language_code="en")
        page.principles.first().delete()
        quiet("import_content", "--update")
        self.assertEqual(PrinciplesPage.objects.get(locale__language_code="en").principles.count(), 10)


class AdminPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        quiet("seed_content")
        User = get_user_model()
        cls.admin = User.objects.create_superuser("root", "root@example.org", "pw-12345")
        cls.editor = User.objects.create_user("pr", "pr@example.org", "pw-12345")
        from django.contrib.auth.models import Group

        cls.editor.groups.add(Group.objects.get(name="روابط عمومی"))

    def zip_of_package(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for path in DEFAULT_DIR.rglob("*"):
                if path.is_file():
                    zf.write(path, Path("content") / path.relative_to(DEFAULT_DIR))
        return SimpleUploadedFile("content.zip", buf.getvalue(), content_type="application/zip")

    def test_only_superusers(self):
        self.client.force_login(self.editor)
        response = self.client.get("/admin/content-import/")
        self.assertNotEqual(response.status_code, 200)  # Wagtail sends them back to the dashboard
        self.assertNotContains(self.client.get("/admin/"), "درون‌ریزی محتوا")

    def test_preview_then_import_uploaded_zip(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/content-import/")
        self.assertContains(response, "درون‌ریزی محتوا")
        Member.objects.filter(slug="armoz").update(summary="ویرایش ادمین")
        response = self.client.post("/admin/content-import/",
                                    {"package": self.zip_of_package(), "mode": "update", "apply": "0"})
        self.assertContains(response, "پیش‌نمایش")
        self.assertEqual(Member.objects.get(slug="armoz").summary, "ویرایش ادمین")
        response = self.client.post("/admin/content-import/",
                                    {"package": self.zip_of_package(), "mode": "update", "apply": "1"})
        self.assertContains(response, "درون‌ریزی انجام شد")
        self.assertNotEqual(Member.objects.get(slug="armoz").summary, "ویرایش ادمین")

    def test_not_a_zip(self):
        self.client.force_login(self.admin)
        response = self.client.post("/admin/content-import/", {
            "package": SimpleUploadedFile("x.zip", b"not a zip"), "mode": "missing", "apply": "1"})
        self.assertContains(response, "zip")
