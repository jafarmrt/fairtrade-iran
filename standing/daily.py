"""
The daily run of the dues and suspension rules (section 1.7). Every step
records the day it ran on the Dues row, so running twice sends nothing twice.
"""

import datetime

from django.db import transaction
from django.utils import timezone

from core.models import MembershipSettings
from members.models import Member
from membership.jalali import format_jalali

from . import notifications
from .models import Decision, Dues, DuesPayment
from .services import COMMISSION, SECRETARIAT, SYSTEM, decide, issue_due


def run(today=None):
    ms = MembershipSettings.load()
    today = today or timezone.localdate()
    report = {"issued": 0, "reminded": 0, "warned": 0, "suspended": 0}
    digest = {SECRETARIAT: [], COMMISSION: []}

    if ms.dues_enabled:
        report["issued"] = len(issue_due(today, ms))

    open_dues = Dues.objects.filter(status=Dues.Status.UNPAID).select_related("member")
    open_dues = open_dues.exclude(member__status=Member.CANCELLED)

    # Reminder shortly before the deadline.
    remind_from = today + datetime.timedelta(days=ms.dues_reminder_days_before)
    for dues in open_dues.filter(reminded_on__isnull=True, due_date__gte=today, due_date__lte=remind_from):
        dues.reminded_on = today
        dues.save(update_fields=["reminded_on"])
        notifications.dues_reminder(dues)
        report["reminded"] += 1

    # Written warning once the deadline has passed.
    for dues in open_dues.filter(warned_on__isnull=True, due_date__lt=today):
        if not ms.dues_auto_warning:
            digest[SECRETARIAT].append(
                f"- مهلت حق عضویت {dues.year} «{dues.member}» گذشته است؛ اخطار کتبی را بفرستید.\n  "
                f"{notifications.admin_url(dues.member)}")
            continue
        if dues.member.status == Member.SUSPENDED:
            continue  # the decision history already carries a suspension; no new warning needed
        with transaction.atomic():
            dues.warned_on = today
            dues.save(update_fields=["warned_on"])
            decide(dues.member, Decision.Kind.WARNING, Decision.Reason.DUES, body=SYSTEM, dues=dues, today=today)
        report["warned"] += 1

    # Suspension N months after the warning (section 1.7, "at the secretariat's discretion").
    for dues in open_dues.filter(warned_on__isnull=False, suspension_flagged_on__isnull=True):
        when = dues.suspension_date(ms)
        if when is None or when > today:
            continue
        member = dues.member
        dues.suspension_flagged_on = today
        dues.save(update_fields=["suspension_flagged_on"])
        if member.status not in (Member.TRIAL, Member.OFFICIAL):
            continue
        if ms.dues_auto_suspend:
            decide(member, Decision.Kind.SUSPEND, Decision.Reason.DUES, body=SYSTEM, dues=dues, today=today)
            report["suspended"] += 1
            digest[SECRETARIAT].append(
                f"- «{member}» به دلیل پرداخت نکردن حق عضویت {dues.year} خودکار تعلیق شد.\n  "
                f"{notifications.admin_url(member)}")
        else:
            digest[SECRETARIAT].append(
                f"- سه ماه از اخطار حق عضویت {dues.year} «{member}» گذشته است؛ درباره تعلیق تصمیم بگیرید.\n  "
                f"{notifications.admin_url(member)}")

    # Suspensions that reached their end: lift or cancel (sections 1.7 and 1.8).
    for member in Member.objects.filter(status=Member.SUSPENDED, suspended_until__lte=today):
        last = member.decisions.filter(kind=Decision.Kind.SUSPEND).order_by("-created_at").first()
        body = COMMISSION if last and last.decided_by == COMMISSION else SECRETARIAT
        digest[body].append(
            f"- مدت تعلیق «{member}» در {format_jalali(member.suspended_until)} تمام شده است؛ "
            f"تعلیق را رفع کنید یا عضویت را لغو کنید.\n  {notifications.admin_url(member)}")

    pending = DuesPayment.objects.filter(status=DuesPayment.Status.PENDING).count()
    if pending:
        digest[SECRETARIAT].append(f"- {pending} رسید حق عضویت در انتظار بررسی است.\n  "
                                   f"{notifications.admin_url()}?show=pending")

    report["digests"] = sum(1 for role, lines in digest.items() if notifications.staff_digest(role, lines))
    return report
