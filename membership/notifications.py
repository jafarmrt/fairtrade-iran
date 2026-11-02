"""E-mails for the membership workflow. Texts come from EmailTemplate snippets."""

import logging
from collections import defaultdict

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.mail import send_mail
from django.db.models import Q
from django.urls import reverse
from django.utils import translation
from wagtail.models import Locale

from core.models import SiteSettings

from .email_defaults import DEFAULT_EMAILS
from .jalali import format_jalali
from .models import EmailTemplate, MembershipPage, member_type_label, status_label

logger = logging.getLogger(__name__)


def base_url():
    return settings.WAGTAILADMIN_BASE_URL.rstrip("/")


def membership_page_url(lang, suffix=""):
    try:
        locale = Locale.objects.get(language_code=lang)
    except Locale.DoesNotExist:
        return ""
    page = MembershipPage.objects.live().filter(locale=locale).first()
    if page is None:
        return ""
    url = page.get_url()
    if not url:
        return ""
    if url.startswith("/"):
        url = base_url() + url
    return url + suffix


def admin_url(application=None):
    if application is None:
        return base_url() + reverse("membership_applications:index")
    return base_url() + reverse("membership_applications:detail", args=[application.pk])


def format_date(value, lang):
    if not value:
        return "-"
    return format_jalali(value) if lang == "fa" else value.strftime("%d %B %Y")


def recipients_for(role):
    """Active users with the role's permission (through a group or directly), plus the house's address."""
    codename = {"secretariat": "secretariat_actions", "commission": "commission_actions"}[role]
    perm = Permission.objects.filter(content_type__app_label="membership", codename=codename).first()
    emails = set()
    if perm is not None:
        users = get_user_model().objects.filter(is_active=True).filter(
            Q(groups__permissions=perm) | Q(user_permissions=perm)
        ).exclude(email="").distinct()
        emails.update(u.email for u in users)
    if role == "secretariat":
        notify = SiteSettings.load().notification_email
        if notify:
            emails.add(notify)
    return sorted(emails)


class SafeDict(defaultdict):
    def __missing__(self, key):
        return "{" + key + "}"


def render(event, lang, context):
    template = EmailTemplate.objects.filter(event=event).first()
    if template is not None:
        if not template.active:
            return None
        subject, body = template.subject, template.body
        if lang == "en" and template.subject_en and template.body_en:
            subject, body = template.subject_en, template.body_en
    else:
        default = DEFAULT_EMAILS.get(event)
        if default is None:
            return None
        subject, body = default[0], default[1]
        if lang == "en" and default[2]:
            subject, body = default[2], default[3]
    values = SafeDict(str, context)
    return subject.format_map(values).replace("\n", " "), body.format_map(values)


def application_context(application, lang, message=""):
    with translation.override(lang):
        site_settings = SiteSettings.load()
        certificate = application.certificate_or_none
        number = certificate.number if certificate else ""
        return {
            "name": application.name_en if (lang == "en" and application.name_en) else application.name,
            "code": application.tracking_code,
            "type": member_type_label(application.member_type),
            "status": status_label(application.status),
            "deadline": format_date(application.deadline, lang),
            "message": message,
            "track_url": membership_page_url(lang, "track/"),
            "admin_url": admin_url(application),
            "certificate_number": number,
            "certificate_url": membership_page_url(lang, f"certificate/?number={number}") if number else "",
            "site_name": site_settings.tr("site_name"),
        }


def send(event, to, lang, context):
    if not to:
        return False
    rendered = render(event, lang, context)
    if rendered is None:
        return False
    subject, body = rendered
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, to)
    except Exception:  # an e-mail problem must never lose an application
        logger.exception("Could not send membership e-mail %s", event)
        return False
    return True


def to_applicant(application, event, message=""):
    lang = application.language if application.language in ("fa", "en") else "fa"
    return send(event, [application.email], lang, application_context(application, lang, message))


def to_role(role, application, event):
    return send(event, recipients_for(role), "fa", application_context(application, "fa"))


# ---- workflow hooks ----


def submitted(application, request=None):
    to_applicant(application, "received")
    to_role("secretariat", application, "staff_new")


def status_changed(application, event, request=None):
    to_applicant(application, f"status_{application.status}", event.message)


def to_commission(application, request=None):
    to_role("commission", application, "commission_new")


def resubmitted(application, request=None):
    role = "commission" if application.status == "commission" else "secretariat"
    to_role(role, application, "staff_resubmitted")
