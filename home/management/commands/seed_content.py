"""
Load the starting content of the site: languages, home pages, user groups,
document collections with their privacy rules, logos, and then everything in
the content package (`content/` folder: pages in Persian and English, members,
form questions, e-mails, SMS texts and settings; see content/README-fa.md).

Safe to run more than once: anything that already exists is left alone,
so edits made in the admin panel are never overwritten. To replace texts with
the package's, use `python manage.py import_content --update`.

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

from core.models import MembershipSettings, SiteSettings
from home.content_import import Importer, fresh
from home.content_package import ContentPackage
from home.models import HomePage
from members.seed import seed_directory
from sms.seed import ensure_sms_templates
from wholesale.seed import ensure_wholesale

from . import seed_data as data


class Command(BaseCommand):
    help = "Load starting content (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--content", help="Content package folder or .zip (default: the content/ folder)")

    @transaction.atomic
    def handle(self, *args, **options):
        self.seed(ContentPackage(options.get("content")), update=False)
        self.stdout.write(self.style.SUCCESS("Starting content is in place."))

    def seed(self, package, update=False):
        """Everything seed_content does; import_content calls this with update=True. Returns the report."""
        self.package = package
        fa, en = self.ensure_locales()
        home_fa, home_en = self.ensure_home_pages(fa, en)
        self.ensure_logos()
        self.ensure_groups_and_collections()
        self.ensure_editorial_workflow(home_fa, home_en)
        report = Importer(package, update=update, stdout=self.stdout).run(fresh(home_fa), fresh(home_en))
        MembershipSettings.load()
        seed_directory(self)
        self.ensure_membership()
        ensure_wholesale(self)
        ensure_sms_templates(self.stdout)
        return report

    # ---- languages and home pages ----

    def ensure_locales(self):
        fa, _ = Locale.objects.get_or_create(language_code="fa")
        en, _ = Locale.objects.get_or_create(language_code="en")
        return fa, en

    def package_values(self, page, lang):
        Importer(self.package)._apply(page, self.package.page("home"), lang)

    def ensure_home_pages(self, fa, en):
        root = Page.get_first_root_node()
        # The tree's invisible top page is called "Root" in English in the admin's page browser.
        Page.objects.filter(pk=root.pk, title="Root").update(title=data.ROOT_TITLE, draft_title=data.ROOT_TITLE)
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
            home_fa = HomePage(locale=fa)
            self.package_values(home_fa, "fa")
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
            self.package_values(home_en, "en")
            home_en.save_revision().publish()
            self.stdout.write("Created English home page")
        return home_fa, home_en.specific

    # ---- settings and logos ----

    def ensure_logos(self):
        site_settings = SiteSettings.load()
        changed = False
        if site_settings.logo_id is None:
            site_settings.logo = self.load_image("logo-navy.png", "لوگو - نسخه تیره")
            changed = True
        if site_settings.logo_light_id is None:
            site_settings.logo_light = self.load_image("logo-white.png", "لوگو - نسخه روشن")
            changed = True
        if changed:
            site_settings.save()

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

    def ensure_membership(self):
        from membership.seed import ensure_membership, ensure_permissions

        ensure_membership(self.stdout)
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
            GroupApprovalTask, GroupCollectionPermission, GroupPagePermission, Task, Workflow, WorkflowPage,
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
        # Images are all public, so the editors may use every collection.
        for code in ("add_image", "change_image", "choose_image"):
            perm = Permission.objects.get(content_type__app_label="wagtailimages", codename=code)
            for group in (pr, board):
                GroupCollectionPermission.objects.get_or_create(group=group, collection=root, permission=perm)
        # Documents: only the collections each group may open (seed_data.DOCUMENT_EDITORS).
        doc_perms = [Permission.objects.get(content_type__app_label="wagtaildocs", codename=code)
                     for code in ("add_document", "change_document", "choose_document")]
        # Earlier versions gave the PR group and the board these rights on the root collection,
        # which let them see confidential commission files and move them to the public collection.
        GroupCollectionPermission.objects.filter(group__in=(pr, board), collection=root,
                                                 permission__in=doc_perms).delete()
        for group_name, collection_names in data.DOCUMENT_EDITORS.items():
            group = Group.objects.get(name=group_name)
            for collection in root.get_children().filter(name__in=collection_names):
                for perm in doc_perms:
                    GroupCollectionPermission.objects.get_or_create(group=group, collection=collection,
                                                                    permission=perm)

        workflow, created = Workflow.objects.get_or_create(name=data.EDITORIAL_WORKFLOW)
        if created:
            task = GroupApprovalTask.objects.create(name=data.EDITORIAL_TASK)
            task.groups.set([board])
            WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)
            self.stdout.write(f"Created workflow {workflow.name}")
        # Wagtail's own starter workflow and task are called "Moderators approval"; they show in the
        # «گردش کار» lists and the editor's «ارسال برای …» button, so give them a Persian name.
        Workflow.objects.filter(name="Moderators approval").update(name="تأیید گروه ناظران")
        Task.objects.filter(name="Moderators approval").update(name="تأیید گروه ناظران")
        for home in (home_fa, home_en):
            # An admin may later pick another workflow for a page; keep that choice.
            if not WorkflowPage.objects.filter(page=home).exists():
                WorkflowPage.objects.create(page=home, workflow=workflow)
