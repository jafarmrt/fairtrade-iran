"""
Appeals of applicants who were rejected before the trial period. They have
no member panel account, so they appeal from the application tracking page,
which they reach with their tracking code and e-mail.
"""

import datetime

from django.db import transaction
from django.utils import timezone

from core.models import is_english

from . import notifications
from .forms import ApplicantAppealForm
from .models import Appeal, AppealSettings

# Application statuses an applicant without a panel account can appeal.
APPEALABLE = {"rejected", "not_accepted"}


def decision_date(application):
    event = application.events.filter(to_status=application.status).order_by("-created_at").first()
    when = event.created_at if event else application.status_changed_at
    return timezone.localtime(when).date()


def appeal_state(application):
    """(can_appeal, deadline, existing appeals) for the tracking page."""
    appeals = list(application.appeals.all())
    settings = AppealSettings.load()
    from members.models import Member

    # Someone with a member profile has a panel account and appeals from the panel.
    has_profile = Member.objects.filter(application=application).exists()
    if not settings.enabled or application.status not in APPEALABLE or appeals or has_profile:
        return False, None, appeals
    deadline = decision_date(application) + datetime.timedelta(days=settings.window_days)
    return deadline >= timezone.localdate(), deadline, appeals


def tracking_context(application, data=None, files=None):
    can_appeal, deadline, appeals = appeal_state(application)
    return {
        "appeal_form": ApplicantAppealForm(data, files) if can_appeal else None,
        "appeal_deadline": deadline,
        "appeals": appeals,
    }


def submit(application, data, files):
    """Handle the tracking page's appeal form. Returns (appeal or None, context)."""
    context = tracking_context(application, data, files)
    form = context["appeal_form"]
    if form is None or not form.is_valid():
        return None, context
    with transaction.atomic():
        appeal = form.save(commit=False)
        appeal.application = application
        appeal.member_name = application.name
        appeal.email = application.email
        appeal.decision = Appeal.Decision.REJECTION
        appeal.decision_body = Appeal.Body.COMMISSION
        appeal.decision_date = decision_date(application)
        appeal.language = "en" if is_english() else "fa"
        appeal.save()
        transaction.on_commit(lambda: notifications.submitted(appeal))
    return appeal, context
