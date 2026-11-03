"""E-mails (texts in AssemblySettings) and SMS (sms_events.py) to the members on an assembly's roll."""

import datetime
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone, translation

from core.jalali import format_jalali
from core.models import SiteSettings
from membership.jalali import persian_digits
from membership.notifications import SafeDict, base_url
from sms import notify as sms_notify
from standing.notifications import member_language, member_phone, member_recipients

from .models import Assembly, AssemblySettings

logger = logging.getLogger(__name__)


def when(value, lang):
    if not value:
        return ""
    if lang == "en":
        return timezone.localtime(value).strftime("%d %B %Y, %H:%M")
    return format_jalali(value, with_time=True)


def assembly_title(assembly, lang):
    return (assembly.title_en or assembly.title) if lang == "en" else assembly.title


def agenda_text(assembly, lang):
    lines = []
    for n, item in enumerate(assembly.items.all(), start=1):
        title = (item.title_en or item.title) if lang == "en" else item.title
        number = str(n) if lang == "en" else persian_digits(n)
        lines.append(f"{number}. {title}")
    return "\n".join(lines)


def results_text(assembly, lang):
    from .services import option_label

    lines = []
    with translation.override(lang):
        for item in assembly.items.filter(counted_at__isnull=False):
            r = item.result or {}
            title = (item.title_en or item.title) if lang == "en" else item.title
            if item.kind == item.Kind.ELECTION:
                names = [option_label(o) for o in r.get("options", []) if o["id"] in r.get("elected", [])]
                outcome = (", " if lang == "en" else "، ").join(names) or ("no one elected" if lang == "en" else "منتخبی ندارد")
            elif r.get("passed"):
                outcome = "approved" if lang == "en" else "تصویب شد"
            else:
                outcome = "not approved" if lang == "en" else "تصویب نشد"
            lines.append(f"- {title}: {outcome}")
    return "\n".join(lines)


def panel_url(member, assembly, lang):
    with translation.override(lang):
        return base_url() + reverse("panel:assembly", kwargs={"member_id": member.pk, "pk": assembly.pk})


def context(assembly, member, lang, **extra):
    with translation.override(lang):
        location = (assembly.location_en or assembly.location) if lang == "en" else assembly.location
        ctx = {
            "name": member.tr("name"),
            "assembly": assembly_title(assembly, lang),
            "date": when(assembly.starts_at, lang),
            "mode": assembly.mode_display,
            "location": (("Place: " if lang == "en" else "محل: ") + location) if location else "",
            "agenda": agenda_text(assembly, lang),
            "panel_url": panel_url(member, assembly, lang),
            "site_name": SiteSettings.load().tr("site_name"),
        }
    ctx.update(extra)
    return ctx


def _email(kind, member, lang, ctx, s):
    to = member_recipients(member)
    if not to:
        return False
    subject, body = getattr(s, f"{kind}_subject"), getattr(s, f"{kind}_body")
    if lang == "en" and getattr(s, f"{kind}_subject_en") and getattr(s, f"{kind}_body_en"):
        subject, body = getattr(s, f"{kind}_subject_en"), getattr(s, f"{kind}_body_en")
    values = SafeDict(str, ctx)
    try:
        send_mail(subject.format_map(values).replace("\n", " "), body.format_map(values),
                  settings.DEFAULT_FROM_EMAIL, to)
    except Exception:  # an e-mail problem must never stop the assembly
        logger.exception("Could not send assembly e-mail %s", kind)
        return False
    return True


def to_roll(assembly, kind, participants=None, extra=None):
    """Send one kind of message to members on the roll. Returns how many e-mails went out."""
    s = AssemblySettings.load()
    participants = participants if participants is not None else assembly.participants.select_related(
        "member__application")
    sent = 0
    for p in participants:
        member = p.member
        lang = member_language(member)
        more = extra(lang) if extra else {}
        ctx = context(assembly, member, lang, **more)
        sent += _email(kind, member, lang, ctx, s)
        sms_notify(f"assembly_{kind}", member_phone(member), ctx, lang)
    return sent


def invitation(assembly):
    participants = list(assembly.participants.select_related("member__application"))
    sent = to_roll(assembly, "invitation", participants)
    assembly.participants.update(invited_at=timezone.now())
    return sent


def reminder(assembly, participants):
    sent = to_roll(assembly, "reminder", participants)
    assembly.participants.filter(pk__in=[p.pk for p in participants]).update(reminded_at=timezone.now())
    return sent


def voting_open(item):
    assembly = item.assembly

    def extra(lang):
        title = (item.title_en or item.title) if lang == "en" else item.title
        closes = ""
        if item.closes_at:
            closes = f" (until {when(item.closes_at, 'en')})" if lang == "en" else f" (تا {when(item.closes_at, 'fa')})"
        return {"item": title, "closes": closes}

    # Members in the room vote on paper; everyone else may vote online.
    participants = [p for p in assembly.participants.select_related("member__application", "proxy_holder")
                    if not (p.is_present and p.votes_on_paper) and not p.proxy_holder_id]
    return to_roll(assembly, "voting", participants, extra)


def results(assembly):
    return to_roll(assembly, "results", extra=lambda lang: {"results": results_text(assembly, lang)})


def send_reminders(now=None):
    """Daily: remind the roll of assemblies that start within `reminder_days_before` days."""
    s = AssemblySettings.load()
    if not s.reminder_days_before:
        return 0
    now = now or timezone.now()
    horizon = now + datetime.timedelta(days=s.reminder_days_before)
    total = 0
    for assembly in Assembly.objects.filter(status=Assembly.Status.INVITED, starts_at__gt=now,
                                            starts_at__lte=horizon):
        due = list(assembly.participants.filter(reminded_at__isnull=True).select_related("member__application"))
        if due:
            total += reminder(assembly, due)
    return total
