"""
Daily job of the shop: cancel orders that were not paid in time and give
their stock back. Runs from deploy/scheduler.sh.

    python manage.py shop_daily
"""

from django.core.management.base import BaseCommand

from shop.services import cancel_overdue


class Command(BaseCommand):
    help = "Cancel shop orders not paid within the payment period set in the shop settings."

    def handle(self, *args, **options):
        self.stdout.write(f"Unpaid orders cancelled: {cancel_overdue()}")
