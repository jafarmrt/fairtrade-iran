"""
Daily job for annual dues and suspensions: issue the year's dues, remind,
send the written warning, suspend after the settings' months, and e-mail the
secretariat and the commission what needs a decision. Runs from
deploy/scheduler.sh with membership_reminders.

    python manage.py membership_standing [--today 2027-03-21]
"""

import datetime

from django.core.management.base import BaseCommand

from standing.daily import run


class Command(BaseCommand):
    help = "Issue annual dues, send reminders and warnings, and suspend members with unpaid dues."

    def add_arguments(self, parser):
        parser.add_argument("--today", type=datetime.date.fromisoformat, help="Run as if today were this date (YYYY-MM-DD)")

    def handle(self, *args, **options):
        report = run(options.get("today"))
        self.stdout.write(
            "Dues issued: {issued}, reminders: {reminded}, warnings: {warned}, suspended: {suspended}, "
            "digest e-mails: {digests}".format(**report))
