"""
E-mail the secretariat and the Supervisory Commission a digest of membership
files whose deadline is near or has passed. Run once a day, e.g. from cron:

    0 8 * * * python manage.py membership_reminders
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import MembershipSettings
from membership.jalali import format_jalali
from membership.models import CLOSED_STATUSES, MembershipApplication, Status
from membership.notifications import admin_url, recipients_for, send

ROLE_STATUSES = {
    "secretariat": {Status.SUBMITTED, Status.APPROVED},
    "commission": {Status.COMMISSION, Status.TRIAL, Status.TRIAL_EXTENDED},
}


class Command(BaseCommand):
    help = "Send deadline reminders for membership files."

    def handle(self, *args, **options):
        ms = MembershipSettings.load()
        today = timezone.localdate()
        limit = today + timezone.timedelta(days=ms.reminder_days_before)
        due = (MembershipApplication.objects.exclude(status__in=CLOSED_STATUSES)
               .filter(deadline__isnull=False, deadline__lte=limit).order_by("deadline"))
        sent = 0
        for role, statuses in ROLE_STATUSES.items():
            items = [a for a in due if a.status in statuses]
            if not items:
                continue
            lines = []
            for a in items:
                state = "گذشته از مهلت" if a.deadline < today else "نزدیک مهلت"
                lines.append(f"- {a.name} ({a.tracking_code}) | {a.get_status_display()} | "
                             f"مهلت: {format_jalali(a.deadline)} | {state}\n  {admin_url(a)}")
            context = {"list": "\n".join(lines), "admin_url": admin_url() + "?status=mine"}
            if send("staff_reminder", recipients_for(role), "fa", context):
                sent += 1
        self.stdout.write(f"Sent {sent} reminder e-mail(s).")
