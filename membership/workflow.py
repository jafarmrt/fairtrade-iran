"""
Who can move a membership file from which status to which, and what happens
when they do (deadlines, trial dates, certificate, e-mails).
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.dispatch import Signal
from django.utils import timezone

from core.models import MembershipSettings

from .jalali import jalali_year
from .models import (
    ApplicationEvent,
    Certificate,
    MembershipApplication,
    Status,
    add_months,
)

SECRETARIAT = "secretariat"
COMMISSION = "commission"

ROLE_PERMS = {
    SECRETARIAT: "membership.secretariat_actions",
    COMMISSION: "membership.commission_actions",
}

# Sent after the secretariat registers a full member, so a members
# directory app can create the public profile.  kwargs: application, certificate
member_registered = Signal()


@dataclass(frozen=True)
class Action:
    key: str
    label: str
    role: str
    sources: frozenset
    target: str = ""  # empty: no status change
    note_required: bool = False
    style: str = ""  # "warning" for negative outcomes
    help: str = ""
    fields: tuple = field(default_factory=tuple)  # extra form fields shown for this action


ACTIONS = [
    # ---- secretariat ----
    Action("confirm_fee", "تأیید دریافت هزینه درخواست", SECRETARIAT,
           frozenset({Status.SUBMITTED, Status.INCOMPLETE})),
    Action("incomplete", "اعلام نقص مدارک به متقاضی", SECRETARIAT,
           frozenset({Status.SUBMITTED}), Status.INCOMPLETE, note_required=True,
           help="در پیام به متقاضی بنویسید چه مدرکی کم است. متقاضی از صفحه پیگیری مدارک را می‌فرستد."),
    Action("to_commission", "کامل است؛ ارسال به کمیسیون نظارتی", SECRETARIAT,
           frozenset({Status.SUBMITTED, Status.INCOMPLETE}), Status.COMMISSION),
    Action("register", "ثبت عضو رسمی و صدور گواهی", SECRETARIAT,
           frozenset({Status.APPROVED}), Status.MEMBER),
    Action("withdraw", "بایگانی پرونده (انصراف یا عدم پیگیری متقاضی)", SECRETARIAT,
           frozenset({Status.SUBMITTED, Status.INCOMPLETE, Status.FIX_REQUESTED, Status.COMMISSION}),
           Status.WITHDRAWN, note_required=True, style="warning"),
    # ---- commission ----
    Action("record_visit", "ثبت بازدید میدانی", COMMISSION,
           frozenset({Status.COMMISSION, Status.TRIAL, Status.TRIAL_EXTENDED}),
           fields=("field_visit_date", "field_visit_report")),
    Action("accept_trial", "رأی: پذیرش آزمایشی", COMMISSION,
           frozenset({Status.COMMISSION}), Status.TRIAL, fields=("decision_reference",)),
    Action("request_fix", "رأی: درخواست اصلاح", COMMISSION,
           frozenset({Status.COMMISSION}), Status.FIX_REQUESTED, note_required=True,
           fields=("decision_reference",)),
    Action("reject", "رأی: رد مستدل", COMMISSION,
           frozenset({Status.COMMISSION}), Status.REJECTED, note_required=True, style="warning",
           fields=("decision_reference",), help="دلیل رد را در پیام به متقاضی بنویسید (رد باید مستدل باشد)."),
    Action("make_member", "ارزیابی پایانی: تبدیل به عضو رسمی", COMMISSION,
           frozenset({Status.TRIAL, Status.TRIAL_EXTENDED}), Status.APPROVED, fields=("decision_reference",)),
    Action("extend_trial", "ارزیابی پایانی: تمدید یکباره دوره آزمایشی", COMMISSION,
           frozenset({Status.TRIAL}), Status.TRIAL_EXTENDED, fields=("decision_reference",)),
    Action("not_accept", "ارزیابی پایانی: عدم پذیرش", COMMISSION,
           frozenset({Status.TRIAL, Status.TRIAL_EXTENDED}), Status.NOT_ACCEPTED, note_required=True,
           style="warning", fields=("decision_reference",)),
]
ACTIONS_BY_KEY = {a.key: a for a in ACTIONS}

# The applicant answers a request from the tracking page.
APPLICANT_RESUBMIT = {
    Status.INCOMPLETE: Status.SUBMITTED,
    Status.FIX_REQUESTED: Status.COMMISSION,
}


class WorkflowError(Exception):
    pass


def user_roles(user):
    if not user.is_authenticated:
        return set()
    return {role for role, perm in ROLE_PERMS.items() if user.has_perm(perm)}


def available_actions(application, user):
    roles = user_roles(user)
    actions = []
    for action in ACTIONS:
        if action.role not in roles or application.status not in action.sources:
            continue
        if action.key == "confirm_fee" and application.fee_confirmed:
            continue
        if action.key == "extend_trial" and application.was_extended:
            continue
        actions.append(action)
    return actions


def blocking_reason(application, action):
    """Why an action cannot be taken yet, or an empty string."""
    if action.key == "to_commission" and application.fee_required and not application.fee_confirmed:
        return "پیش از ارسال به کمیسیون، دریافت هزینه درخواست را تأیید کنید."
    if action.key == "accept_trial" and application.is_producer and not application.field_visit_date:
        return "برای تولیدکنندگان، بازدید میدانی پیش از رأی پذیرش الزامی است (بند ۱.۴). ابتدا بازدید را ثبت کنید."
    return ""


def deadline_for(status, today, ms, application):
    if status in (Status.SUBMITTED, Status.APPROVED):
        return today + timezone.timedelta(days=ms.secretariat_review_days)
    if status == Status.COMMISSION:
        return today + timezone.timedelta(days=ms.commission_review_days)
    if status in (Status.TRIAL, Status.TRIAL_EXTENDED):
        return application.trial_ends_on
    return None


def _enter_status(application, status, ms, today):
    if status == Status.TRIAL:
        application.trial_starts_on = today
        application.trial_ends_on = add_months(today, ms.trial_period_months)
    elif status == Status.TRIAL_EXTENDED:
        application.trial_ends_on = add_months(application.trial_ends_on or today, ms.trial_period_months)
    application.status = status
    application.status_changed_at = timezone.now()
    application.deadline = deadline_for(status, today, ms, application)


def issue_certificate(application, ms=None):
    ms = ms or MembershipSettings.load()
    existing = Certificate.objects.filter(application=application).first()
    if existing:
        return existing
    today = timezone.localdate()
    valid_until = add_months(today, ms.certificate_validity_months) if ms.certificate_validity_months else None
    return Certificate.objects.create(
        application=application,
        number=Certificate.next_number(ms.certificate_prefix or "FTH", jalali_year(today)),
        name=application.name,
        name_en=application.name_en,
        member_type=application.member_type,
        issued_on=today,
        valid_until=valid_until,
    )


@transaction.atomic
def perform(application, action_key, user, message="", internal_note="", decision_reference="",
            field_visit_date=None, field_visit_report="", request=None):
    """Run a staff action. Raises WorkflowError when it is not allowed."""
    from . import notifications

    action = ACTIONS_BY_KEY.get(action_key)
    if action is None or action not in available_actions(application, user):
        raise WorkflowError("این اقدام برای شما یا در این وضعیت مجاز نیست.")
    reason = blocking_reason(application, action)
    if reason:
        raise WorkflowError(reason)
    if action.note_required and not message.strip():
        raise WorkflowError("برای این اقدام، نوشتن پیام به متقاضی لازم است.")

    ms = MembershipSettings.load()
    today = timezone.localdate()
    from_status = application.status

    if action.key == "confirm_fee":
        application.fee_confirmed_at = timezone.now()
    if action.key == "record_visit":
        if not field_visit_date:
            raise WorkflowError("تاریخ بازدید را وارد کنید.")
        application.field_visit_date = field_visit_date
        application.field_visit_report = field_visit_report
    if action.target:
        _enter_status(application, action.target, ms, today)
    application.save()

    certificate = None
    if action.key == "register":
        certificate = issue_certificate(application, ms)

    event = ApplicationEvent.objects.create(
        application=application, user=user, action=action.key,
        from_status=from_status, to_status=action.target or "",
        message=message.strip(), internal_note=internal_note.strip(),
        decision_reference=decision_reference.strip(),
    )

    if action.target:
        transaction.on_commit(lambda: notifications.status_changed(application, event, request=request))
        if action.target == Status.COMMISSION:
            transaction.on_commit(lambda: notifications.to_commission(application, request=request))
    if certificate is not None:
        transaction.on_commit(
            lambda: member_registered.send(sender=MembershipApplication, application=application,
                                           certificate=certificate)
        )
    return event


@transaction.atomic
def applicant_resubmit(application, message, request=None):
    """The applicant sent the missing documents or the requested changes."""
    from . import notifications

    target = APPLICANT_RESUBMIT.get(application.status)
    if target is None:
        raise WorkflowError("در این وضعیت امکان ارسال مدارک نیست.")
    from_status = application.status
    _enter_status(application, target, MembershipSettings.load(), timezone.localdate())
    application.save()
    event = ApplicationEvent.objects.create(
        application=application, action="applicant_resubmit", from_status=from_status, to_status=target,
        internal_note=("پیام متقاضی: " + message.strip()) if message.strip() else "",
    )
    transaction.on_commit(lambda: notifications.resubmitted(application, request=request))
    return event

