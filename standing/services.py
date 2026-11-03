"""
What happens to a member's dues and standing: issuing yearly dues, receipts,
confirming payments, and decisions (notice, warning, suspension, lifting,
cancellation, reinstatement) with their side effects.
"""

import datetime

from django.db import transaction
from django.utils import timezone

from core.models import MembershipSettings
from members.models import Member
from membership.jalali import jalali_year, to_gregorian, to_jalali
from membership.models import add_months

from .models import Decision, Dues, DuesPayment

SECRETARIAT = Decision.Body.SECRETARIAT
COMMISSION = Decision.Body.COMMISSION
SYSTEM = Decision.Body.SYSTEM

ROLE_PERMS = {
    SECRETARIAT: "membership.secretariat_actions",
    COMMISSION: "membership.commission_actions",
}

R = Decision.Reason
K = Decision.Kind

# Which body decides, by reason (section 7: dues matters by the secretariat,
# standards matters by the commission; section 1.7/1.8 for each reason).
REASON_BODY = {
    R.DUES: {SECRETARIAT},
    R.RESIGNATION: {SECRETARIAT},
    R.DISSOLUTION: {SECRETARIAT},
    R.PAID: {SECRETARIAT},
    R.MINOR: {COMMISSION},
    R.AUDIT: {COMMISSION},
    R.INSPECTION: {COMMISSION},
    R.COMPLAINT: {COMMISSION},
    R.SERIOUS: {COMMISSION},
    R.LONG_SUSPENSION: {SECRETARIAT, COMMISSION},
    R.RESOLVED: {SECRETARIAT, COMMISSION},
    R.APPEAL: {SECRETARIAT, COMMISSION},
    R.OTHER: {SECRETARIAT, COMMISSION},
}

# Reasons allowed for each kind of decision.
KIND_REASONS = {
    K.NOTICE: [R.MINOR, R.OTHER],
    K.WARNING: [R.DUES, R.AUDIT, R.MINOR, R.OTHER],
    K.SUSPEND: [R.DUES, R.AUDIT, R.INSPECTION, R.COMPLAINT],
    K.LIFT: [R.PAID, R.RESOLVED, R.APPEAL],
    K.CANCEL: [R.RESIGNATION, R.SERIOUS, R.LONG_SUSPENSION, R.DISSOLUTION],
    K.REINSTATE: [R.APPEAL],
}

# Member statuses each kind of decision can start from.
ACTIVE = (Member.TRIAL, Member.OFFICIAL)
KIND_FROM = {
    K.NOTICE: ACTIVE + (Member.SUSPENDED,),
    K.WARNING: ACTIVE + (Member.SUSPENDED,),
    K.SUSPEND: ACTIVE,
    K.LIFT: (Member.SUSPENDED,),
    K.CANCEL: ACTIVE + (Member.SUSPENDED,),
    K.REINSTATE: (Member.CANCELLED,),
}


class StandingError(Exception):
    pass


def user_bodies(user):
    if not user or not user.is_authenticated:
        return set()
    return {body for body, perm in ROLE_PERMS.items() if user.has_perm(perm)}


def can_view(user):
    return bool(user_bodies(user)) or (user and user.is_authenticated and user.has_perm("standing.view_dues"))


def reason_choices_for(kind, bodies):
    return [(r, R(r).label) for r in KIND_REASONS[kind] if REASON_BODY[r] & set(bodies)]


def available_kinds(member, bodies):
    return [k for k in K if member.status in KIND_FROM[k] and reason_choices_for(k, bodies)]


# ---------------------------------------------------------------------------
# Membership years
# ---------------------------------------------------------------------------


def liable(member, ms):
    statuses = {Member.OFFICIAL, Member.SUSPENDED} | ({Member.TRIAL} if ms.dues_for_trial else set())
    return member.status in statuses


def period_for(member, today, ms, ahead_days=0):
    """
    The latest membership year that starts on or before today + ahead_days:
    (jalali year, start date). Uses the fixed yearly date, or the member's
    joining anniversary.
    """
    limit = today + datetime.timedelta(days=ahead_days)
    if ms.dues_cycle == ms.DUES_ANNIVERSARY and member.joined_on:
        start = member.joined_on
        while add_months(start, 12) <= limit:
            start = add_months(start, 12)
        return jalali_year(start), start
    jy = to_jalali(limit.year, limit.month, limit.day)[0] + 1
    while True:
        start = to_gregorian(jy, ms.dues_start_month, ms.dues_start_day)
        if start <= limit:
            return jy, start
        jy -= 1


def create_dues(member, year, start, ms, due_date=None):
    """Create the dues for one year, or return the existing one. None if no fee is set for the type."""
    existing = Dues.objects.filter(member=member, year=year).first()
    if existing:
        return existing, False
    amount = ms.annual_fee_for(member.member_type)
    if not amount:
        return None, False
    dues = Dues.objects.create(
        member=member, year=year, period_start=start, amount=amount,
        due_date=due_date or start + datetime.timedelta(days=ms.dues_payment_days),
    )
    from . import notifications

    transaction.on_commit(lambda: notifications.dues_issued(dues))
    return dues, True


def issue_due(today=None, ms=None):
    """
    Create the dues of members whose membership year starts within the
    issuing window. A year whose payment deadline has already passed is not
    billed automatically (e.g. on the first run after installing); the
    secretariat can issue it by hand from the member's page.
    Returns the new Dues rows.
    """
    ms = ms or MembershipSettings.load()
    today = today or timezone.localdate()
    created = []
    for member in Member.objects.exclude(status=Member.CANCELLED):
        if not liable(member, ms):
            continue
        year, start = period_for(member, today, ms, ahead_days=ms.dues_issue_days_before)
        if today > start + datetime.timedelta(days=ms.dues_payment_days):
            continue
        # Do not bill a year that began before the member joined.
        if member.joined_on and start < member.joined_on:
            continue
        dues, new = create_dues(member, year, start, ms)
        if new:
            created.append(dues)
    return created


def issue_by_hand(member, today=None, ms=None):
    """The secretariat issues the current year's dues; the member gets the full payment period from today."""
    ms = ms or MembershipSettings.load()
    today = today or timezone.localdate()
    year, start = period_for(member, today, ms)
    due = max(start, today) + datetime.timedelta(days=ms.dues_payment_days)
    dues, new = create_dues(member, year, start, ms, due_date=due)
    if dues is None:
        raise StandingError("مبلغ حق عضویت سالانه این نوع عضویت در «تنظیمات عضویت» وارد نشده است.")
    if not new:
        raise StandingError("حق عضویت این سال پیش‌تر ثبت شده است.")
    return dues


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


@transaction.atomic
def submit_receipt(dues, user, amount, reference="", paid_on_text="", receipt=None, note=""):
    if not dues.can_pay:
        raise StandingError("برای این سال رسیدی در انتظار بررسی است یا پرداخت کامل شده است.")
    payment = DuesPayment(dues=dues, amount=amount, reference=reference, paid_on_text=paid_on_text,
                          payer_note=note, submitted_by=user)
    if receipt:
        payment.original_name = receipt.name[:255]
        payment.receipt = receipt
    payment.save()
    dues.status = Dues.Status.PENDING
    dues.save(update_fields=["status"])
    from . import notifications

    transaction.on_commit(lambda: notifications.receipt_received(payment))
    return payment


@transaction.atomic
def record_payment(dues, user, amount, reference="", note=""):
    """The secretariat records a payment it received another way, and confirms it."""
    if not dues.is_open:
        raise StandingError("این حق عضویت باز نیست.")
    payment = DuesPayment.objects.create(
        dues=dues, amount=amount, reference=reference, payer_note=note, submitted_by=user,
        recorded_by_staff=True, status=DuesPayment.Status.PENDING,
    )
    return review_payment(payment, user, confirm=True)


@transaction.atomic
def review_payment(payment, user, confirm, message=""):
    if payment.status != DuesPayment.Status.PENDING:
        raise StandingError("این رسید پیش‌تر بررسی شده است.")
    if not confirm and not message.strip():
        raise StandingError("بنویسید چرا رسید پذیرفته نشد؛ این پیام برای عضو فرستاده می‌شود.")
    dues = payment.dues
    payment.status = DuesPayment.Status.CONFIRMED if confirm else DuesPayment.Status.REJECTED
    payment.reviewed_by = user
    payment.reviewed_at = timezone.now()
    payment.staff_message = message.strip()
    payment.save()
    if confirm:
        dues.status = Dues.Status.PAID
        dues.paid_on = timezone.localdate()
        dues.closed_by = user
    elif not dues.payments.filter(status=DuesPayment.Status.PENDING).exists():
        dues.status = Dues.Status.UNPAID
    dues.save()
    from . import notifications

    if not payment.recorded_by_staff:
        transaction.on_commit(lambda: notifications.payment_reviewed(payment))
    if confirm:
        _lift_if_debt_cleared(dues.member, user)
    return payment


@transaction.atomic
def waive(dues, user, note=""):
    if not dues.is_open:
        raise StandingError("این حق عضویت باز نیست.")
    dues.status = Dues.Status.WAIVED
    dues.closed_by = user
    if note.strip():
        dues.internal_note = (dues.internal_note + "\n" if dues.internal_note else "") + note.strip()
    dues.save()
    _lift_if_debt_cleared(dues.member, user)
    return dues


def _lift_if_debt_cleared(member, user):
    """Section 1.7: once the debt that caused a suspension is cleared, lift it (if the settings say so)."""
    ms = MembershipSettings.load()
    member.refresh_from_db()
    if not ms.dues_lift_on_payment or member.status != Member.SUSPENDED:
        return None
    last = member.decisions.filter(kind=K.SUSPEND).order_by("-created_at").first()
    if last is None or last.reason != R.DUES:
        return None
    if member.dues.filter(status=Dues.Status.UNPAID, due_date__lt=timezone.localdate()).exists():
        return None
    return decide(member, K.LIFT, R.PAID, user=None, body=SYSTEM,
                  message="بدهی حق عضویت پرداخت شد و تعلیق عضویت رفع شد.",
                  message_en="The membership fee has been paid and the suspension is lifted.")


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

CERT_SUSPENDED = "تعلیق عضویت"
CERT_CANCELLED = "لغو عضویت"


def _certificate(member):
    application = member.application
    if application is None:
        return None
    from membership.models import Certificate

    return Certificate.objects.filter(application=application).first()


def _set_services(member, active):
    """Members' group (member-only documents) for the people who manage this member."""
    from django.contrib.auth.models import Group

    from memberpanel.onboarding import MEMBERS_GROUP

    group = Group.objects.filter(name=MEMBERS_GROUP).first()
    if group is None:
        return
    users = list(member.managers.all())
    if active:
        group.user_set.add(*users)
        return
    for user in users:
        still_active = user.managed_members.exclude(pk=member.pk).exclude(status__in=Member.INACTIVE_STATUSES)
        if not still_active.exists():
            group.user_set.remove(user)


@transaction.atomic
def decide(member, kind, reason, user=None, body=None, message="", message_en="", internal_note="",
           decision_reference="", months=None, dues=None, today=None):
    """Record a decision and apply it. `body` is the deciding body; checked against the user's roles."""
    ms = MembershipSettings.load()
    today = today or timezone.localdate()
    if member.status not in KIND_FROM[kind]:
        raise StandingError("این اقدام در وضعیت فعلی عضو ممکن نیست.")
    if reason not in KIND_REASONS[kind]:
        raise StandingError("این دلیل برای این اقدام پذیرفته نیست.")
    if body != SYSTEM:
        bodies = user_bodies(user) & REASON_BODY[reason]
        if body is None:
            body = SECRETARIAT if SECRETARIAT in bodies else next(iter(bodies), None)
        if body not in bodies:
            raise StandingError("ثبت این رأی با نقش شما نیست.")
    if kind in (K.SUSPEND, K.CANCEL) and body == COMMISSION and not decision_reference.strip():
        raise StandingError("آرای تعلیق و لغو کمیسیون جمعی است؛ شماره یا تاریخ صورتجلسه را بنویسید.")

    decision = Decision(member=member, kind=kind, reason=reason, decided_by=body, decided_on=today,
                        message=message.strip(), internal_note=internal_note.strip(),
                        decision_reference=decision_reference.strip(), created_by=user, dues=dues,
                        from_status=member.status)
    if kind in (K.WARNING, K.SUSPEND, K.CANCEL, K.NOTICE):
        decision.appeal_until = today + datetime.timedelta(days=ms.appeal_days)

    certificate = _certificate(member)
    if kind == K.SUSPEND:
        months = min(max(int(months or ms.suspension_max_months), 1), ms.suspension_max_months)
        decision.ends_on = add_months(today, months)
        member.status_before_suspension = member.status
        member.status = Member.SUSPENDED
        member.suspended_until = decision.ends_on
        if certificate and not certificate.revoked:
            certificate.revoked, certificate.revoked_reason = True, CERT_SUSPENDED
            certificate.save()
        _set_services(member, False)
    elif kind in (K.LIFT, K.REINSTATE):
        member.status = member.status_before_suspension or Member.OFFICIAL
        member.suspended_until = None
        member.cancelled_on = None
        member.reapply_after = None
        if certificate and certificate.revoked and certificate.revoked_reason in (CERT_SUSPENDED, CERT_CANCELLED):
            certificate.revoked, certificate.revoked_reason = False, ""
            certificate.save()
        _set_services(member, True)
    elif kind == K.CANCEL:
        if member.status != Member.SUSPENDED:
            member.status_before_suspension = member.status
        months_wait = ms.reapply_after_serious_months if reason == R.SERIOUS else ms.reapply_after_months
        decision.reapply_after = add_months(today, months_wait)
        member.status = Member.CANCELLED
        member.suspended_until = None
        member.cancelled_on = today
        member.reapply_after = decision.reapply_after
        if certificate and (not certificate.revoked or certificate.revoked_reason == CERT_SUSPENDED):
            certificate.revoked, certificate.revoked_reason = True, CERT_CANCELLED
            certificate.save()
        _set_services(member, False)
    member.save()
    decision.to_status = member.status
    decision.save()

    from . import notifications

    transaction.on_commit(lambda: notifications.decision_made(decision, message_en=message_en))
    return decision
