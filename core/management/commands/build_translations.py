"""
Compile the project's .po translation files (locale/*/LC_MESSAGES/*.po)
into the .mo files Django loads. Run it after editing a .po file:

    python manage.py build_translations

Unlike Django's compilemessages it needs no GNU gettext on the machine.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core import pofile


class Command(BaseCommand):
    help = "Compile locale/*/LC_MESSAGES/*.po into .mo files (no GNU gettext needed)."

    def handle(self, *args, **options):
        for folder in settings.LOCALE_PATHS:
            for po_path in sorted(Path(folder).glob("*/LC_MESSAGES/*.po")):
                entries = pofile.parse(po_path.read_text(encoding="utf-8"))
                po_path.with_suffix(".mo").write_bytes(pofile.mo_bytes(entries))
                self.stdout.write(f"{po_path.with_suffix('.mo')}: {len(entries)} entries")
