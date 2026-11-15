"""
Put the content package (home/content_package.py) into the database.

Two modes:

- "missing" (the default, used by `seed_content`): only creates what is not
  there yet. Anything that already exists, and every edit made in the admin
  panel, is left alone.
- "update" (`import_content --update`, or «جایگزینی» in the admin page):
  also replaces the texts of existing pages, members, questions, e-mails and
  settings with the package's texts. Pages get a new published revision, so
  an earlier version can be restored from the page's history.

In both modes members listed under `withdrawn` in members.yaml stop being
founding members, and phrases listed in checks.yaml are searched for on the
site afterwards.
"""

import datetime
import json

from django.apps import apps
from django.db import models
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Collection, Locale, Page

PAGE_REF = "page"  # a field value {page: key} points to another page of the package


def fresh(page):
    """Reload a page so treebeard's child counters are current before adding or copying."""
    return type(page).objects.get(pk=page.pk)


def to_stream(blocks):
    """Package blocks ([{heading: …}, {paragraph: …}] or [{type, value}]) → StreamField raw data."""
    raw = []
    for block in blocks or []:
        if isinstance(block, dict) and "type" in block and "value" in block:
            raw.append({"type": block["type"], "value": block["value"]})
        elif isinstance(block, dict) and len(block) == 1:
            (kind, value), = block.items()
            raw.append({"type": kind, "value": value})
        else:
            raise ValueError(f"Bad block: {block!r}")
    return raw


def _strip_ids(value):
    if isinstance(value, dict):
        return {k: _strip_ids(v) for k, v in value.items() if k != "id"}
    if isinstance(value, list):
        return [_strip_ids(v) for v in value]
    return value


def _norm_stream(field, value):
    """Comparable form of a StreamField value (stored value or package raw data)."""
    block = field.stream_block
    if isinstance(value, list):
        value = block.to_python(value)
    return json.dumps(_strip_ids(block.get_prep_value(value)), ensure_ascii=False, sort_keys=True)


class Importer:
    def __init__(self, package, update=False, stdout=None):
        self.pkg = package
        self.update = update
        self.stdout = stdout
        self.report = []  # (action, what) — action: created / updated / changed / warning
        self.pages = {}   # key → (page_fa, page_en)

    def log(self, action, what):
        self.report.append((action, what))
        if self.stdout is not None:
            self.stdout.write(f"{action}: {what}")

    # ================= entry points =================

    def run(self, home_fa=None, home_en=None):
        """Everything in the package. Home pages must exist (seed_content creates them)."""
        fa, en = Locale.objects.get(language_code="fa"), Locale.objects.get(language_code="en")
        if home_fa is None:
            home_fa = Page.objects.get(locale=fa, depth=2, content_type__model="homepage").specific
            home_en = home_fa.get_translation(en).specific
        self.locales = (fa, en)
        self.import_settings()
        self.import_regions_and_categories()
        self.import_pages(home_fa, home_en)
        self.import_members()
        self.withdraw_members()
        self.import_questions()
        self.import_emails()
        self.import_sms()
        self.check_phrases()
        return self.report

    # ================= pages =================

    def import_pages(self, home_fa, home_en):
        home_spec = self.pkg.page("home")
        self.pages["home"] = (fresh(home_fa), fresh(home_en))
        if self.update:
            self._update_page(self.pages["home"][0], home_spec, "fa")
            self._update_page(self.pages["home"][1], home_spec, "en")
        for spec in self.pkg.pages:
            if spec["key"] == "home":
                continue
            if self.pages.get(spec.get("parent")) is None:
                continue  # parent was skipped
            self.pages[spec["key"]] = self.ensure_page(spec)
        # Second pass: links between pages (hero button, complaint page) and from settings.
        for spec in self.pkg.pages:
            if self.pages.get(spec["key"]) is None:
                continue
            page_fa, page_en = self.pages[spec["key"]]
            for page, lang in ((page_fa, "fa"), (page_en, "en")):
                self._set_page_refs(fresh(page).specific, spec, lang)
            link = spec.get("site_settings_link")
            if link:
                self._link_setting(link, page_fa)

    def _model(self, spec):
        return apps.get_model(spec["type"])

    def _find(self, model, spec, locale):
        slug = spec["fa"]["slug"] if spec["key"] != "home" else None
        page = model.objects.filter(locale=locale, slug=slug).first()
        if page is None and spec["type"] in self._singletons():
            page = model.objects.filter(locale=locale).first()
        return page

    @staticmethod
    def _singletons():
        from .content_package import SINGLETON_TYPES
        return SINGLETON_TYPES

    def ensure_page(self, spec):
        model = self._model(spec)
        fa, en = self.locales
        parent_fa, parent_en = self.pages[spec["parent"]]
        page_fa = self._find(model, spec, fa)
        label = f"{spec['key']} ({spec['fa']['title']})"
        if page_fa is None and spec.get("only_on_new_site") and model.objects.exists():
            return None  # e.g. the launch news: not added again to a site that already has news
        if page_fa is None:
            page_fa = model(show_in_menus=spec.get("in_menu", True))
            self._apply(page_fa, spec, "fa")
            fresh(parent_fa).add_child(instance=page_fa)
            self._apply_relations(page_fa, spec, "fa")
            page_fa.save_revision().publish()
            self._place_after_previous_sibling(page_fa, spec)
            self.log("created", f"page {label} [fa]")
        elif self.update:
            self._update_page(page_fa, spec, "fa")
        page_fa = fresh(page_fa)
        page_en = page_fa.get_translation_or_none(en)
        if page_en is None:
            page_en = page_fa.copy_for_translation(en).specific
            self._apply(page_en, spec, "en")
            self._apply_relations(page_en, spec, "en")
            page_en.save_revision().publish()
            self._place_after_previous_sibling(page_en, spec, lang=1)
            self.log("created", f"page {label} [en]")
        else:
            page_en = page_en.specific
            if self.update:
                self._update_page(page_en, spec, "en")
        return fresh(page_fa).specific, fresh(page_en).specific

    def _place_after_previous_sibling(self, page, spec, lang=0):
        """A page added to an existing site goes where the package puts it (menu order), not last."""
        previous = None
        for other in self.pkg.pages:
            if other is spec:
                break
            if other.get("parent") == spec.get("parent") and self.pages.get(other["key"]):
                previous = self.pages[other["key"]][lang]
        page = fresh(page)
        if previous is not None and page.get_prev_sibling() is not None \
                and page.get_prev_sibling().pk != previous.pk:
            page.move(fresh(previous), pos="right")

    def _values(self, model, spec, lang):
        """Simple field values for one language (relations and page links are handled apart)."""
        values = {}
        for name, value in (spec.get(lang) or {}).items():
            field = model._meta.get_field(name)
            if field.many_to_one or field.one_to_many:
                continue
            if isinstance(field, StreamField):
                value = to_stream(value)
            elif isinstance(field, models.DateField) and isinstance(value, str):
                value = datetime.date.fromisoformat(value)
            elif isinstance(value, str) and isinstance(field, (RichTextField, models.TextField, models.CharField)):
                value = value.strip()
            values[name] = value
        return values

    def _apply(self, page, spec, lang):
        for name, value in self._values(type(page), spec, lang).items():
            if isinstance(page._meta.get_field(name), StreamField):
                value = json.dumps(value, ensure_ascii=False)
            setattr(page, name, value)

    def _relation_rows(self, model, spec, lang):
        """{relation name: [kwargs, …]} for inline lists (principles, form fields, document sections)."""
        rows = {}
        for name, value in (spec.get(lang) or {}).items():
            field = model._meta.get_field(name)
            if not field.one_to_many:
                continue
            related = field.related_model
            items = []
            for order, item in enumerate(value or []):
                kwargs = dict(item)
                if "collection" in kwargs:
                    kwargs["collection"] = Collection.get_first_root_node().get_children().filter(
                        name=kwargs["collection"]).first()
                    if kwargs["collection"] is None:
                        continue  # collection missing (created by seed_content); skip quietly
                if hasattr(related, "sort_order"):
                    kwargs.setdefault("sort_order", order)
                items.append(kwargs)
            rows[name] = (related, items)
        return rows

    def _apply_relations(self, page, spec, lang):
        for name, (related, items) in self._relation_rows(type(page), spec, lang).items():
            setattr(page, name, [related(**kwargs) for kwargs in items])

    def _relations_differ(self, page, spec, lang):
        for name, (related, items) in self._relation_rows(type(page), spec, lang).items():
            current = list(getattr(page, name).all())
            if len(current) != len(items):
                return True
            for obj, kwargs in zip(current, items):
                for key, value in kwargs.items():
                    if key == "sort_order":
                        continue
                    if getattr(obj, key) != value:
                        return True
        return False

    def _update_page(self, page, spec, lang):
        page = fresh(page).specific
        changed = []
        for name, value in self._values(type(page), spec, lang).items():
            field = page._meta.get_field(name)
            current = getattr(page, name)
            if isinstance(field, StreamField):
                if _norm_stream(field, current) != _norm_stream(field, value):
                    setattr(page, name, json.dumps(value, ensure_ascii=False))
                    changed.append(name)
            elif current != value:
                if name == "slug" and page.get_parent().get_children().filter(slug=value).exclude(pk=page.pk).exists():
                    continue
                setattr(page, name, value)
                changed.append(name)
        if self._relations_differ(page, spec, lang):
            self._apply_relations(page, spec, lang)
            changed.append("items")
        if changed:
            page.save_revision().publish()
            self.log("updated", f"page {spec['key']} [{lang}]: {', '.join(changed)}")

    def _set_page_refs(self, page, spec, lang):
        changed = []
        for name, value in (spec.get(lang) or {}).items():
            if not (isinstance(value, dict) and PAGE_REF in value):
                continue
            if value[PAGE_REF] not in self.pages:
                self.log("warning", f"{spec['_file']}: page '{value[PAGE_REF]}' not in the package")
                continue
            target = self.pages[value[PAGE_REF]]
            if target is None:
                continue
            target = target[0 if lang == "fa" else 1]
            current_id = getattr(page, f"{name}_id")
            if current_id is None or (self.update and current_id != target.pk):
                setattr(page, name, target)
                changed.append(name)
        if changed:
            page.save_revision().publish()

    def _link_setting(self, field, page_fa):
        from core.models import SiteSettings

        site_settings = SiteSettings.load()
        if getattr(site_settings, f"{field}_id") is None:
            setattr(site_settings, field, page_fa)
            site_settings.save()

    # ================= settings =================

    def import_settings(self):
        for label, values in (self.pkg.site.get("settings") or {}).items():
            model = apps.get_model(label)
            obj = model.load()
            changed = []
            for name, value in (values or {}).items():
                field = model._meta.get_field(name)
                if field.is_relation:
                    continue
                if isinstance(value, str):
                    value = value.strip()
                current = getattr(obj, name)
                empty = current in ("", None) or (field.has_default() and current == field.get_default())
                if current != value and (self.update or empty):
                    setattr(obj, name, value)
                    changed.append(name)
            if changed:
                obj.save()
                self.log("updated", f"settings {model._meta.verbose_name}: {', '.join(changed)}")

    # ================= regions, categories, members =================

    def import_regions_and_categories(self):
        from members.models import Region
        from products.models import Category

        for order, row in enumerate(self.pkg.members.get("regions", [])):
            obj, created = Region.objects.get_or_create(
                name=row["name"], defaults={"name_en": row.get("name_en", ""), "sort_order": order})
            if not created and self.update and obj.name_en != row.get("name_en", obj.name_en):
                obj.name_en = row["name_en"]
                obj.save()
        for order, row in enumerate(self.pkg.members.get("categories", [])):
            obj = Category.objects.filter(slug=row["slug"]).first() or Category.objects.filter(name=row["name"]).first()
            if obj is None:
                Category.objects.create(name=row["name"], name_en=row.get("name_en", ""), slug=row["slug"],
                                        sort_order=order)
                self.log("created", f"category {row['name']}")
            elif self.update and (obj.name, obj.name_en) != (row["name"], row.get("name_en", "")):
                obj.name, obj.name_en = row["name"], row.get("name_en", "")
                obj.save()
                self.log("updated", f"category {row['name']}")

    MEMBER_FIELDS = ("name", "name_en", "member_type", "is_founding", "city", "city_en", "summary", "summary_en",
                     "story", "story_en", "instagram_url", "website_url", "public_email", "sort_order",
                     "is_featured")

    def import_members(self):
        from members.models import Member, Region

        for order, row in enumerate(self.pkg.members.get("members", [])):
            values = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k in self.MEMBER_FIELDS}
            values.setdefault("sort_order", order + 1)
            region = Region.objects.filter(name=row["region"]).first() if row.get("region") else None
            member = Member.objects.filter(slug=row["slug"]).first()
            if member is None:
                Member.objects.create(
                    slug=row["slug"], status=row.get("status", Member.OFFICIAL), region=region,
                    is_featured=row.get("is_featured", True), **{k: v for k, v in values.items() if k != "is_featured"},
                )
                self.log("created", f"member {row['name']}")
                continue
            if not self.update:
                continue
            changed = [k for k, v in values.items() if getattr(member, k) != v]
            for k in changed:
                setattr(member, k, values[k])
            if row.get("region") and member.region_id != getattr(region, "pk", None):
                member.region = region
                changed.append("region")
            if changed:
                member.save()
                self.log("updated", f"member {row['name']}: {', '.join(changed)}")

    def withdraw_members(self):
        """Members who are no longer founding members: never shown as founders, and hidden if asked."""
        from django.db.models import Q

        from members.models import Member

        for row in self.pkg.members.get("withdrawn", []):
            query = Q(slug__in=row.get("slugs", []))
            for name in row.get("names", []):
                query |= Q(name=name) | Q(name_en=name)
            for member in Member.objects.filter(query):
                changed = []
                if member.is_founding:
                    member.is_founding = False
                    changed.append("is_founding")
                if member.is_featured:
                    member.is_featured = False
                    changed.append("is_featured")
                if row.get("hide") and member.is_published:
                    member.is_published = False
                    changed.append("is_published")
                if changed:
                    member.save()
                    self.log("changed", f"member {member.name} is no longer a founding member ({', '.join(changed)})")

    # ================= membership form, e-mails, SMS =================

    def import_questions(self):
        from membership.models import ApplicationQuestion

        if not self.pkg.questions:
            return
        if not self.update and ApplicationQuestion.objects.exists():
            return  # the secretariat already shaped the form; leave it alone
        for order, q in enumerate(self.pkg.questions):
            values = {
                "label": q["label"].strip(), "label_en": q.get("label_en", "").strip(),
                "help_text": q.get("help", "").strip(), "help_text_en": q.get("help_en", "").strip(),
                "field_type": q["type"], "required": q.get("required", True),
                "choices": "\n".join(q.get("choices", [])), "choices_en": "\n".join(q.get("choices_en", [])),
                "sort_order": (order + 1) * 10, "active": q.get("active", True),
                **{f"for_{t}": t in (q.get("for") or []) for t in ("producer", "institution", "network", "individual")},
            }
            obj = ApplicationQuestion.objects.filter(label=values["label"]).first()
            if obj is None:
                ApplicationQuestion.objects.create(**values)
                self.log("created", f"question {values['label']}")
                continue
            changed = [k for k, v in values.items() if getattr(obj, k) != v]
            if changed:
                for k in changed:
                    setattr(obj, k, values[k])
                obj.save()
                self.log("updated", f"question {values['label']}: {', '.join(changed)}")

    def import_emails(self):
        from membership.models import EmailTemplate

        for event, texts in self.pkg.emails.items():
            if event not in EmailTemplate.Event.values:
                self.log("warning", f"emails.yaml: unknown event '{event}'")
                continue
            values = {k: (texts.get(k) or "").strip() for k in ("subject", "body", "subject_en", "body_en")}
            obj, created = EmailTemplate.objects.get_or_create(event=event, defaults=values)
            if created:
                self.log("created", f"e-mail {event}")
            elif self.update and any(getattr(obj, k) != v for k, v in values.items()):
                for k, v in values.items():
                    setattr(obj, k, v)
                obj.save()
                self.log("updated", f"e-mail {event}")

    def import_sms(self):
        from sms import registry
        from sms.models import SmsTemplate

        for key, texts in self.pkg.sms.items():
            if registry.get(key) is None:
                self.log("warning", f"sms.yaml: unknown event '{key}'")
                continue
            values = {"text": (texts.get("text") or "").strip(), "text_en": (texts.get("text_en") or "").strip()}
            obj, created = SmsTemplate.objects.get_or_create(
                event=key, defaults=dict(values, active=texts.get("active", registry.get(key).active)))
            if created:
                self.log("created", f"SMS {key}")
            elif self.update and any(getattr(obj, k) != v for k, v in values.items()):
                for k, v in values.items():
                    setattr(obj, k, v)
                obj.save()
                self.log("updated", f"SMS {key}")

    # ================= checks =================

    def check_phrases(self):
        """Warn about phrases that must not appear any more (e.g. a former founding member)."""
        for hit in find_phrases(self.pkg.checks.get("forbidden_phrases", [])):
            self.log("warning", hit)


def find_phrases(phrases):
    """Where on the live site do these phrases still appear? Returns readable locations."""
    from members.models import Member

    hits = []
    phrases = [p for p in phrases if p]
    if not phrases:
        return hits
    for page in Page.objects.live().specific():
        text = json.dumps(page.serializable_data(), ensure_ascii=False, default=str)
        for phrase in phrases:
            if phrase in text:
                hits.append(f"«{phrase}» still appears on page {page.url_path} (id {page.pk})")
    for member in Member.objects.filter(is_published=True):
        text = " ".join(str(getattr(member, f) or "") for f in ("name", "name_en", "summary", "summary_en",
                                                                 "story", "story_en"))
        for phrase in phrases:
            if phrase in text:
                hits.append(f"«{phrase}» still appears in published member {member.name} (id {member.pk})")
    for label in ("core.SiteSettings", "core.SeoSettings"):
        obj = apps.get_model(label).load()
        text = " ".join(str(getattr(obj, f.name) or "") for f in obj._meta.concrete_fields)
        for phrase in phrases:
            if phrase in text:
                hits.append(f"«{phrase}» still appears in {label}")
    return hits
