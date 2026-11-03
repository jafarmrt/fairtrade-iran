"""
Daily job of the General Assembly: count votes whose time has ended and remind
members of assemblies that start soon (AssemblySettings.reminder_days_before).

    python manage.py assembly_daily
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from assembly import notifications
from assembly.models import Assembly
from assembly.services import finalize_due


class Command(BaseCommand):
    help = "Count finished votes and send assembly reminders."

    def handle(self, *args, **options):
        for assembly in Assembly.objects.filter(status=Assembly.Status.IN_SESSION):
            finalize_due(assembly)
        sent = notifications.send_reminders(timezone.now())
        self.stdout.write(f"assembly reminders sent: {sent}")
