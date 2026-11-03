"""
Load the starting content of the site: languages, home pages, About and
Ten Principles pages (Persian and English), logos and site settings, user
groups, and document collections with their privacy rules.

Safe to run more than once: anything that already exists is left alone,
so edits made in the admin panel are never overwritten.

    python manage.py seed_content
"""

import os
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.images.models import Image
from wagtail.models import Collection, CollectionViewRestriction, Locale, Page, Site

from archive.models import DocumentsPage, DocumentsSection
from contact.models import ComplaintPage, ContactFormField, ContactPage
from core.models import MembershipSettings, SiteSettings
from home.models import HomePage
from news.models import NewsIndexPage, NewsPage
from members.seed import seed_directory
from pages.models import Principle, PrinciplesPage, StandardPage
from sms.seed import ensure_sms_templates
from wholesale.seed import ensure_wholesale

from . import seed_data as data


def fresh(page):
    """Reload a page so treebeard's child counters are current before adding or copying."""
    return type(page).objects.get(pk=page.pk)


class Command(BaseCommand):
    help = "Load starting content (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        fa, en = self.ensure_locales()
        home_fa, home_en = self.ensure_home_pages(fa, en)
        about_fa, about_en = self.ensure_page(home_fa, home_en, StandardPage, data.ABOUT, order_hint="about")
        for home, about in ((fresh(home_fa), about_fa), (fresh(home_en), about_en)):
            if home.hero_cta_page_id is None:
                home.hero_cta_page = about
                home.save_revision().publish()
        self.ensure_principles(home_fa, home_en)
        self.ensure_settings()
        self.ensure_groups_and_collections()
        self.ensure_editorial_workflow(home_fa, home_en)
        self.ensure_news(home_fa, home_en)
        self.ensure_documents_page(home_fa, home_en)
        self.ensure_contact_pages(home_fa, home_en)
        seed_directory(self, home_fa, home_en)
        self.ensure_membership(home_fa, home_en)
        ensure_wholesale(self, home_fa, home_en)
        ensure_sms_templates(self.stdout)
        self.stdout.write(self.style.SUCCESS("Starting content is in place."))

    # ---- languages and home pages ----

    def ensure_locales(self):
        fa, _ = Locale.objects.get_or_create(language_code="fa")
        en, _ = Locale.objects.get_or_create(language_code="en")
        return fa, en

    def ensure_home_pages(self, fa, en):
        root = Page.get_first_root_node()
        site = Site.objects.filter(is_default_site=True).first()

        home_fa = HomePage.objects.filter(locale=fa).first()
        if home_fa is None:
            # Remove Wagtail's placeholder "Welcome" page if it is still there.
            for child in root.get_children():
                if child.specific_class is Page and child.slug == "home":
                    if site and site.root_page_id == child.id:
                        site.root_page = root
                        site.save()
                    child.delete()
            root = Page.objects.get(pk=root.pk)  # refresh tree counters after the delete
            home_fa = HomePage(locale=fa, **data.HOME["fa"])
            root.add_child(instance=home_fa)
            home_fa.save_revision().publish()
            self.stdout.write("Created Persian home page")

        if site is None:
            site = Site.objects.create(hostname="localhost", port=80, root_page=home_fa,
                                       is_default_site=True, site_name=settings.WAGTAIL_SITE_NAME)
        elif site.root_page_id != home_fa.id:
            site.root_page = home_fa
            site.site_name = settings.WAGTAIL_SITE_NAME
            site.save()

        # Full links (sitemap, e-mails) use the Site's address: take it from SITE_URL once.
        site_url = urlparse(os.environ.get("SITE_URL", ""))
        if site_url.hostname and site.hostname == "localhost" and site_url.hostname != "localhost":
            site.hostname = site_url.hostname
            site.port = site_url.port or (443 if site_url.scheme == "https" else 80)
            site.save()

        home_fa = fresh(home_fa)
        home_en = home_fa.get_translation_or_none(en)
        if home_en is None:
            home_en = home_fa.copy_for_translation(en)
            home_en = home_en.specific
            for field, value in data.HOME["en"].items():
                setattr(home_en, field, value)
            home_en.save_revision().publish()
            self.stdout.write("Created English home page")
        return home_fa, home_en.specific

    def ensure_page(self, home_fa, home_en, model, content, order_hint=""):
        page_fa = model.objects.filter(locale=home_fa.locale, slug=content["fa"]["slug"]).first()
        if page_fa is None:
            page_fa = model(show_in_menus=True, **content["fa"])
            fresh(home_fa).add_child(instance=page_fa)
            page_fa.save_revision().publish()
            self.stdout.write(f"Created {order_hint} page (fa)")
        page_fa = fresh(page_fa)
        page_en = page_fa.get_translation_or_none(home_en.locale)
        if page_en is None:
            page_en = page_fa.copy_for_translation(home_en.locale).specific
            for field, value in content["en"].items():
                setattr(page_en, field, value)
            page_en.save_revision().publish()
            self.stdout.write(f"Created {order_hint} page (en)")
        return page_fa, page_en

    def ensure_principles(self, home_fa, home_en):
        page_fa = PrinciplesPage.objects.filter(locale=home_fa.locale).first()
        if page_fa is None:
            page_fa = PrinciplesPage(show_in_menus=True, **data.PRINCIPLES_PAGE["fa"])
            page_fa.principles = [Principle(title=t, description=d) for t, d in data.PRINCIPLES_FA]
            fresh(home_fa).add_child(instance=page_fa)
            page_fa.save_revision().publish()
            self.stdout.write("Created principles page (fa)")
        page_fa = fresh(page_fa)
        if page_fa.get_translation_or_none(home_en.locale) is None:
            page_en = page_fa.copy_for_translation(home_en.locale).specific
            for field, value in data.PRINCIPLES_PAGE["en"].items():
                setattr(page_en, field, value)
            page_en.principles = [Principle(title=t, description=d) for t, d in data.PRINCIPLES_EN]
            page_en.save_revision().publish()
            self.stdout.write("Created principles page (en)")

    # ---- settings and logos ----

    def ensure_settings(self):
        site_settings = SiteSettings.load()
        changed = False
        if site_settings.logo_id is None:
            site_settings.logo = self.load_image("logo-navy.png", "لوگو - نسخه تیره")
            changed = True
        if site_settings.logo_light_id is None:
            site_settings.logo_light = self.load_image("logo-white.png", "لوگو - نسخه روشن")
            changed = True
        for field, value in data.SITE_SETTINGS.items():
            if not getattr(site_settings, field):
                setattr(site_settings, field, value)
                changed = True
        if changed:
            site_settings.save()
        MembershipSettings.load()

    def load_image(self, filename, title):
        existing = Image.objects.filter(title=title).first()
        if existing:
            return existing
        path = os.path.join(settings.PROJECT_DIR, "static", "img", filename)
        with open(path, "rb") as fh:
            image = Image(title=title, file=ImageFile(fh, name=filename))
            image.save()
        return image

    # ---- membership (page, form questions, e-mails, permissions) ----

    def ensure_membership(self, home_fa, home_en):
        from membership.seed import ensure_membership, ensure_permissions

        ensure_membership(home_fa, home_en, self.stdout, fresh=fresh)
        ensure_permissions(*(Group.objects.filter(name=n).first()
                             for n in (data.SECRETARIAT, data.COMMISSION, data.BOARD)))

    # ---- groups and document collections ----

    def ensure_groups_and_collections(self):
        access_admin = Permission.objects.get(content_type__app_label="wagtailadmin", codename="access_admin")
        groups = {}
        for name in data.GROUPS:
            group, created = Group.objects.get_or_create(name=name)
            if name != data.MEMBERS_GROUP:
                group.permissions.add(access_admin)
            groups[name] = group

        root = Collection.get_first_root_node()
        for name, allowed_groups in data.COLLECTIONS:
            collection = root.get_children().filter(name=name).first()
            if collection is None:
                collection = root.add_child(name=name)
                self.stdout.write(f"Created collection {name}")
            if allowed_groups and not CollectionViewRestriction.objects.filter(collection=collection).exists():
                restriction = CollectionViewRestriction.objects.create(
                    collection=collection, restriction_type=CollectionViewRestriction.GROUPS
                )
                restriction.groups.set([groups[g] for g in allowed_groups])

        commission = groups[data.COMMISSION]
        for codename in ("view_complaint", "change_complaint"):
            commission.permissions.add(
                Permission.objects.get(content_type__app_label="contact", codename=codename)
            )
        shop_perms = list(Permission.objects.filter(content_type__app_label="shop", codename__in=[
            "manage_orders", "view_order", "add_seller", "change_seller", "view_seller"]))
        shop_perms += list(Permission.objects.filter(content_type__app_label="payments", codename="view_payment"))
        for name in (data.SECRETARIAT, data.MARKET):
            groups[name].permissions.add(*shop_perms)
        secretary = groups[data.ASSEMBLY_SECRETARY]
        for codename in ("view_appeal", "change_appeal"):
            secretary.permissions.add(
                Permission.objects.get(content_type__app_label="appeals", codename=codename)
            )
        # The Assembly Secretary runs the General Assembly; the board and secretariat follow it.
        secretary.permissions.add(*Permission.objects.filter(
            content_type__app_label="assembly",
            codename__in=["add_assembly", "change_assembly", "view_assembly",
                          "add_agendaitem", "change_agendaitem", "delete_agendaitem", "view_agendaitem"],
        ))
        view_assembly = Permission.objects.get(content_type__app_label="assembly", codename="view_assembly")
        for name in (data.BOARD, data.SECRETARIAT):
            groups[name].permissions.add(view_assembly)

    # ---- editorial workflow: the PR group writes, the board approves ----

    def ensure_editorial_workflow(self, home_fa, home_en):
        from wagtail.models import (
            GroupApprovalTask, GroupCollectionPermission, GroupPagePermission, Workflow, WorkflowPage,
            WorkflowTask,
        )

        pr = Group.objects.get(name=data.PR)
        board = Group.objects.get(name=data.BOARD)
        page_perm = {c: Permission.objects.get(content_type__app_label="wagtailcore", codename=c)
                     for c in ("add_page", "change_page", "publish_page")}
        for home in (home_fa, home_en):
            # The PR group drafts and edits pages but cannot publish; the board can publish.
            for group, codes in ((pr, ("add_page", "change_page")),
                                 (board, ("add_page", "change_page", "publish_page"))):
                for code in codes:
                    GroupPagePermission.objects.get_or_create(group=group, page=home, permission=page_perm[code])
        root = Collection.get_first_root_node()
        for app, model in (("wagtailimages", "image"), ("wagtaildocs", "document")):
            for code in (f"add_{model}", f"change_{model}", f"choose_{model}"):
                perm = Permission.objects.get(content_type__app_label=app, codename=code)
                for group in (pr, board):
                    GroupCollectionPermission.objects.get_or_create(group=group, collection=root, permission=perm)

        workflow, created = Workflow.objects.get_or_create(name=data.EDITORIAL_WORKFLOW)
        if created:
            task = GroupApprovalTask.objects.create(name=data.EDITORIAL_TASK)
            task.groups.set([board])
            WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)
            self.stdout.write(f"Created workflow {workflow.name}")
        for home in (home_fa, home_en):
            # An admin may later pick another workflow for a page; keep that choice.
            if not WorkflowPage.objects.filter(page=home).exists():
                WorkflowPage.objects.create(page=home, workflow=workflow)

    # ---- news, documents, contact ----

    def ensure_translation(self, page_fa, locale_en, values, label):
        """English copy of a Persian page, with the given fields replaced."""
        page_fa = fresh(page_fa)
        page_en = page_fa.get_translation_or_none(locale_en)
        if page_en is not None:
            return page_en.specific
        page_en = page_fa.copy_for_translation(locale_en).specific
        for field, value in values.items():
            setattr(page_en, field, value)
        page_en.save_revision().publish()
        self.stdout.write(f"Created {label} (en)")
        return page_en

    def ensure_news(self, home_fa, home_en):
        index_fa, index_en = self.ensure_page(home_fa, home_en, NewsIndexPage, data.NEWS_INDEX, order_hint="news")
        item = NewsPage.objects.filter(locale=home_fa.locale, slug=data.FIRST_NEWS["fa"]["slug"]).first()
        if item is None and not NewsPage.objects.exists():
            item = NewsPage(**data.FIRST_NEWS["fa"])
            fresh(index_fa).add_child(instance=item)
            item.save_revision().publish()
            self.stdout.write("Created first news item (fa)")
        if item is not None:
            self.ensure_translation(item, home_en.locale, data.FIRST_NEWS["en"], "first news item")

    def ensure_documents_page(self, home_fa, home_en):
        page_fa = DocumentsPage.objects.filter(locale=home_fa.locale).first()
        if page_fa is None:
            page_fa = DocumentsPage(show_in_menus=True, **data.DOCUMENTS_PAGE["fa"])
            page_fa.sections = self.document_sections(lang=0)
            fresh(home_fa).add_child(instance=page_fa)
            page_fa.save_revision().publish()
            self.stdout.write("Created documents page (fa)")
        values = dict(data.DOCUMENTS_PAGE["en"], sections=self.document_sections(lang=1))
        self.ensure_translation(page_fa, home_en.locale, values, "documents page")

    def document_sections(self, lang):
        root = Collection.get_first_root_node()
        sections = []
        for name, heading_fa, heading_en, desc_fa, desc_en, show_locked in data.DOCUMENT_SECTIONS:
            collection = root.get_children().filter(name=name).first()
            if collection is None:
                continue
            sections.append(DocumentsSection(
                collection=collection,
                heading=(heading_fa, heading_en)[lang],
                description=(desc_fa, desc_en)[lang],
                show_when_locked=show_locked,
            ))
        return sections

    def ensure_contact_pages(self, home_fa, home_en):
        complaint_fa = ComplaintPage.objects.filter(locale=home_fa.locale).first()
        if complaint_fa is None:
            complaint_fa = ComplaintPage(show_in_menus=False, **data.COMPLAINT_PAGE["fa"])
            fresh(home_fa).add_child(instance=complaint_fa)
            complaint_fa.save_revision().publish()
            self.stdout.write("Created complaint page (fa)")
        complaint_en = self.ensure_translation(complaint_fa, home_en.locale, data.COMPLAINT_PAGE["en"], "complaint page")

        contact_fa = ContactPage.objects.filter(locale=home_fa.locale).first()
        if contact_fa is None:
            contact_fa = ContactPage(show_in_menus=True, complaint_page=complaint_fa, **data.CONTACT_PAGE["fa"])
            contact_fa.form_fields = self.contact_fields(lang=0)
            fresh(home_fa).add_child(instance=contact_fa)
            contact_fa.save_revision().publish()
            self.stdout.write("Created contact page (fa)")
        values = dict(data.CONTACT_PAGE["en"], complaint_page=complaint_en, form_fields=self.contact_fields(lang=1))
        self.ensure_translation(contact_fa, home_en.locale, values, "contact page")

    def contact_fields(self, lang):
        return [
            ContactFormField(label=(label_fa, label_en)[lang], field_type=field_type, required=required)
            for label_fa, label_en, field_type, required in data.CONTACT_FIELDS
        ]
