"""E-mails about appeals. Member-facing texts come from AppealSettings."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import translation

from core.models import SiteSettings
from membership.notifications import SafeDict, base_url, format_date

from .models import SECRETARY_GROUP, AppealSettings

logger = logging.getLogger(__name__)


def secretary_recipients():
    s = AppealSettings.load()
    emails = set(
        get_user_model().objects.filter(groups__name=SECRETARY_GROUP, is_active=True)
        .exclude(email="").values_list("email", flat=True)
    )
    emails.update(a.strip() for a in s.extra_recipients.split(",") if a.strip())
    if not emails and SiteSettings.load().notification_email:
        emails.add(SiteSettings.load().notification_email)
    return sorted(emails)


def _send(subject, body, to):
    if not to:
        return False
    try:
        send_mail(subject.replace("\n", " "), body, settings.DEFAULT_FROM_EMAIL, to)
    except Exception:  # an e-mail problem must never lose an appeal
        logger.exception("Could not send appeal e-mail")
        return False
    return True


def appeal_context(appeal, lang):
    with translation.override(lang):
        member = appeal.member
        name = member.tr("name") if member else appeal.member_name
        if member:
            panel_url = base_url() + reverse("panel:appeals", args=[member.pk])
        else:
            from membership.notifications import membership_page_url

            panel_url = membership_page_url(lang, "track/")
        return {
            "name": name,
            "code": appeal.tracking_code,
            "decision": appeal.decision_display,
            "status": appeal.status_display,
            "decide_by": format_date(appeal.decide_by, lang),
            "hearing_date": format_date(appeal.hearing_date, lang) if appeal.hearing_date else "",
            "ruling": appeal.ruling,
            "panel_url": panel_url,
            "site_name": SiteSettings.load().tr("site_name"),
        }


def to_member(appeal, kind):
    s = AppealSettings.load()
    lang = "en" if appeal.language == "en" else "fa"
    subject, body = getattr(s, f"{kind}_subject"), getattr(s, f"{kind}_body")
    if lang == "en" and getattr(s, f"{kind}_subject_en") and getattr(s, f"{kind}_body_en"):
        subject, body = getattr(s, f"{kind}_subject_en"), getattr(s, f"{kind}_body_en")
    values = SafeDict(str, appeal_context(appeal, lang))
    return _send(subject.format_map(values), body.format_map(values), [appeal.email] if appeal.email else [])


def to_secretary(appeal):
    with translation.override("fa"):
        link = base_url() + reverse("appeals:edit", args=[appeal.pk])
    body = (
        f"عضو «{appeal.member_name}» به «{appeal.get_decision_display()}» اعتراض کرد.\n"
        f"کد پیگیری: {appeal.tracking_code}\n"
        f"مهلت صدور رأی (بند ۸-۲ سند ارکان): {format_date(appeal.decide_by, 'fa')}\n\n"
        f"برای خواندن اعتراض و رسیدگی وارد بخش مدیریت شوید:\n{link}\n"
    )
    return _send(f"اعتراض تازه: {appeal.tracking_code}", body, secretary_recipients())


def submitted(appeal):
    to_member(appeal, "received")
    to_secretary(appeal)


def status_changed(appeal):
    to_member(appeal, "update")
