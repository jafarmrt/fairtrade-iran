"""
Read the bilingual content package: the texts of the site, kept apart from
the code in YAML files (the `content/` folder at the top of the project, or
a .zip of that folder).

    content/
      site.yaml              settings (names, taglines, footer, contact, SEO, …)
      pages/NN-key.yaml      one page per file, Persian and English together;
                             NN orders the files (a parent before its children)
      members.yaml           regions, shop categories, founding members,
                             members who are no longer founding members
      membership-form.yaml   questions of the membership application form
      emails.yaml            membership e-mail texts
      sms.yaml               SMS texts
      checks.yaml            phrases that must not appear on the site any more

The import itself is in `home/content_import.py`; see content/README-fa.md.
"""

import io
import tempfile
import zipfile
from pathlib import Path

import yaml
from django.conf import settings

DEFAULT_DIR = Path(settings.BASE_DIR) / "content"

# Page types a package may create, and the singleton ones (one per language).
PAGE_TYPES = {
    "home.HomePage", "pages.StandardPage", "pages.PrinciplesPage", "news.NewsIndexPage", "news.NewsPage",
    "archive.DocumentsPage", "contact.ContactPage", "contact.ComplaintPage", "members.MemberIndexPage",
    "products.ProductIndexPage", "membership.MembershipPage", "wholesale.WholesalePage",
}
SINGLETON_TYPES = {
    "home.HomePage", "pages.PrinciplesPage", "news.NewsIndexPage", "archive.DocumentsPage", "contact.ContactPage",
    "contact.ComplaintPage", "members.MemberIndexPage", "products.ProductIndexPage", "membership.MembershipPage",
    "wholesale.WholesalePage",
}
# Settings a package may fill in (text fields only; logos and bank details stay in the admin panel).
SETTINGS_MODELS = {
    "core.SiteSettings", "core.MembershipSettings", "core.SeoSettings", "core.PwaSettings",
    "members.DirectorySettings", "products.ShopSettings", "wholesale.WholesaleSettings",
}
MEMBER_TYPES = {"producer", "institution", "network", "individual"}


class PackageError(Exception):
    """The package is missing or a file in it is malformed. The message is for people, in both languages."""


class ContentPackage:
    def __init__(self, source=None, _data=None):
        self._tmp = None  # keeps an unzipped package on disk while this object lives
        path = Path(source) if source else DEFAULT_DIR
        if _data is not None:
            path = self._unzip(_data)
        if path.is_file() and zipfile.is_zipfile(path):
            path = self._unzip(path.read_bytes())
        self.root = self._find_root(path)
        self.label = str(source or ("upload" if _data is not None else DEFAULT_DIR))
        self.site = self._load("site.yaml", {})
        self.members = self._load("members.yaml", {})
        self.questions = self._load("membership-form.yaml", {}).get("questions", [])
        self.emails = self._load("emails.yaml", {})
        self.sms = self._load("sms.yaml", {})
        self.checks = self._load("checks.yaml", {})
        self.pages = self._load_pages()
        self.validate()

    @classmethod
    def from_upload(cls, uploaded_file):
        """A .zip sent from the admin panel."""
        data = uploaded_file.read()
        if not zipfile.is_zipfile(io.BytesIO(data)):
            raise PackageError("فایل باید zip باشد. / The file must be a .zip of the content folder.")
        pkg = cls(_data=data)
        pkg.label = uploaded_file.name
        return pkg

    # ---- reading ----

    def _unzip(self, data):
        self._tmp = tempfile.TemporaryDirectory(prefix="content-")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                target = (Path(self._tmp.name) / name).resolve()
                if not str(target).startswith(str(Path(self._tmp.name).resolve())):
                    raise PackageError(f"مسیر نامعتبر در zip: {name} / Unsafe path in the zip: {name}")
            zf.extractall(self._tmp.name)
        return Path(self._tmp.name)

    @staticmethod
    def _find_root(path):
        if (path / "site.yaml").exists():
            return path
        # A zip of the folder holds content/site.yaml.
        for candidate in sorted(path.glob("*/site.yaml")):
            return candidate.parent
        raise PackageError(
            f"پوشه محتوا پیدا نشد (site.yaml در {path} نیست). / No content package found (no site.yaml in {path})."
        )

    def _load(self, name, default):
        path = self.root / name
        if not path.exists():
            return default
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise PackageError(f"خطا در فایل {name}: {exc} / Error in {name}: {exc}") from exc
        return data if data is not None else default

    def _load_pages(self):
        pages = []
        for path in sorted((self.root / "pages").glob("*.yaml")):
            spec = self._load(f"pages/{path.name}", {})
            spec["_file"] = f"pages/{path.name}"
            pages.append(spec)
        return pages

    # ---- checking ----

    def validate(self):
        errors = []
        keys = set()
        for spec in self.pages:
            where = spec["_file"]
            key = spec.get("key")
            if not key:
                errors.append(f"{where}: key ندارد / has no key")
                continue
            if key in keys:
                errors.append(f"{where}: key تکراری «{key}» / duplicate key '{key}'")
            if spec.get("type") not in PAGE_TYPES:
                errors.append(f"{where}: نوع صفحه نامعتبر «{spec.get('type')}» / unknown page type")
            parent = spec.get("parent")
            if key != "home" and parent not in keys:
                errors.append(f"{where}: صفحه والد «{parent}» پیش از این فایل نیامده / parent '{parent}' must come first")
            for lang in ("fa", "en"):
                values = spec.get(lang) or {}
                if not values.get("title") or not values.get("slug"):
                    errors.append(f"{where}: {lang}.title و {lang}.slug لازم است / {lang}.title and {lang}.slug are required")
            keys.add(key)
        if "home" not in keys:
            errors.append("pages: صفحه home لازم است / a page with key 'home' is required")
        for model in (self.site.get("settings") or {}):
            if model not in SETTINGS_MODELS:
                errors.append(f"site.yaml: تنظیمات «{model}» پشتیبانی نمی‌شود / settings '{model}' not supported")
        for row in self.members.get("members", []):
            if not row.get("slug") or not row.get("name"):
                errors.append(f"members.yaml: هر عضو slug و name لازم دارد / each member needs slug and name: {row}")
            if row.get("member_type", "producer") not in MEMBER_TYPES:
                errors.append(f"members.yaml: نوع عضویت نامعتبر / bad member_type for {row.get('slug')}")
        for q in self.questions:
            if not q.get("label") or not q.get("type"):
                errors.append(f"membership-form.yaml: هر پرسش label و type لازم دارد / each question needs label and type: {q}")
            if not set(q.get("for") or []) <= MEMBER_TYPES:
                errors.append(f"membership-form.yaml: «for» نامعتبر / bad 'for' in {q.get('label')}")
        if errors:
            raise PackageError("\n".join(errors))

    def page(self, key):
        for spec in self.pages:
            if spec.get("key") == key:
                return spec
        return None

    def summary(self):
        """Counts shown before an import."""
        return {
            "pages": len(self.pages),
            "news": sum(1 for p in self.pages if p.get("type") == "news.NewsPage"),
            "members": len(self.members.get("members", [])),
            "questions": len(self.questions),
            "emails": len(self.emails),
            "sms": len(self.sms),
        }
