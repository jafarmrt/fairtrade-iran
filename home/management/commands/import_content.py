"""
Import the bilingual content package (the content/ folder, or a .zip of it)
in one step.

    python manage.py import_content                 # add only what is missing
    python manage.py import_content --update        # also replace existing texts with the package's
    python manage.py import_content --dry-run       # show what would change, change nothing
    python manage.py import_content --check         # only look for phrases listed in checks.yaml
    python manage.py import_content path/to/content.zip --update

Works on a fresh database too: it does everything seed_content does first
(languages, home pages, groups, collections, permissions).
See content/README-fa.md.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from home.content_import import find_phrases
from home.content_package import ContentPackage, PackageError

from .seed_content import Command as SeedCommand


class DryRun(Exception):
    pass


class Command(BaseCommand):
    help = "Import the bilingual content package (content/ folder or .zip)."

    def add_arguments(self, parser):
        parser.add_argument("source", nargs="?", help="Content folder or .zip (default: the project's content/ folder)")
        parser.add_argument("--update", action="store_true",
                            help="Replace texts of existing pages, members, questions, e-mails and settings")
        parser.add_argument("--dry-run", action="store_true", help="Show what would change; save nothing")
        parser.add_argument("--check", action="store_true",
                            help="Only report where phrases from checks.yaml still appear")

    def handle(self, *args, **options):
        try:
            package = ContentPackage(options.get("source"))
        except PackageError as exc:
            raise CommandError(str(exc)) from exc
        counts = package.summary()
        self.stdout.write(f"Package: {package.label}")
        self.stdout.write(", ".join(f"{k}: {v}" for k, v in counts.items()))

        if options["check"]:
            hits = find_phrases(package.checks.get("forbidden_phrases", []))
            for hit in hits:
                self.stdout.write(self.style.WARNING(hit))
            self.stdout.write(self.style.SUCCESS("No listed phrase found.") if not hits else
                              self.style.ERROR(f"{len(hits)} place(s) to fix."))
            return

        report = run_import(package, update=options["update"], dry_run=options["dry_run"], stdout=self.stdout)
        print_summary(self, report, options["dry_run"])


def run_import(package, update=False, dry_run=False, stdout=None):
    """Shared by the command and the admin page. Returns the report [(action, what), …]."""
    seed = SeedCommand(stdout=stdout)
    report = []
    try:
        with transaction.atomic():
            report = seed.seed(package, update=update)
            if dry_run:
                raise DryRun
    except DryRun:
        pass
    return report


def print_summary(command, report, dry_run):
    counts = {}
    for action, _ in report:
        counts[action] = counts.get(action, 0) + 1
    warnings = [what for action, what in report if action == "warning"]
    prefix = "Dry run (nothing saved). Would have: " if dry_run else "Done: "
    command.stdout.write(command.style.SUCCESS(
        prefix + (", ".join(f"{n} {a}" for a, n in sorted(counts.items())) or "nothing to change")))
    for what in warnings:
        command.stdout.write(command.style.WARNING(what))
