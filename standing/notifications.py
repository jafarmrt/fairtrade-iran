"""E-mails about dues and standing. Texts are EmailTemplate snippets (membership app), with defaults in email_defaults.py."""

from django.urls import reverse
from django.utils import translation

from core.models import MembershipSettings, SiteSettings
from core.templatetags.site_tags import money
from membership.jalali import persian_digits
from membership.notifications import base_url, format_date, recipients_for, send


def member_language(member):
    application = member.application
    lang = application.language if application else "fa"
    return lang if lang in ("fa", "en") else "fa"


def member_recipients(member):
    emails = {u.email for u in member.managers.filter(is_active=True).exclude(email="")}
    if member.application and member.application.email:
        emails.add(member.application.email)
    return sorted(emails)


def panel_url(member, lang):
    with translation.override(lang):
        return base_url() + reverse("panel:membership", kwargs={"member_id": member.pk})


def admin_url(member=None):
    if member is None:
        return base_url() + reverse("standing:index")
    return base_url() + reverse("standing:member", args=[member.pk])


def bank_text(lang):
    ms = MembershipSettings.load()
    rows = [
        ("به نام", "Account holder", ms.account_holder),
        ("بانک", "Bank", ms.bank_name),
        ("شماره کارت", "Card number", ms.card_number),
        ("شماره شبا", "IBAN (Sheba)", ms.sheba),
    ]
    return "\n".join(f"{en if lang == 'en' else fa}: {value}" for fa, en, value in rows if value)


def amount_text(value, lang):
    text = money(value)
    return f"{text} rials" if lang == "en" else f"{persian_digits(text)} ریال"


def context_for(member, lang, dues=None, decision=None, message=""):
    with translation.override(lang):
        ms = MembershipSettings.load()
        ctx = {
            "name": member.tr("name"),
            "member": member.name,
            "panel_url": panel_url(member, lang),
            "admin_url": admin_url(member),
            "site_name": SiteSettings.load().tr("site_name"),
            "bank": bank_text(lang),
            "message": message,
        }
        if dues is not None:
            ctx.update({
                "year": dues.year if lang == "en" else persian_digits(dues.year),
                "amount": amount_text(dues.amount, lang),
                "due_date": format_date(dues.due_date, lang),
                "suspend_date": format_date(dues.suspension_date(ms), lang),
            })
        if decision is not None:
            ctx.update({
                "decision": decision.kind_display,
                "reason": decision.reason_display,
                "decision_reference": decision.decision_reference,
                "until": format_date(decision.ends_on, lang),
                "appeal_until": format_date(decision.appeal_until, lang),
                "reapply_after": format_date(decision.reapply_after, lang),
            })
        return ctx


def to_member(member, event, **kwargs):
    lang = member_language(member)
    return send(event, member_recipients(member), lang, context_for(member, lang, **kwargs))


# ---- hooks ----


def dues_issued(dues):
    return to_member(dues.member, "dues_issued", dues=dues)


def dues_reminder(dues):
    return to_member(dues.member, "dues_reminder", dues=dues)


def dues_warning(dues, decision):
    return to_member(dues.member, "dues_warning", dues=dues, decision=decision, message=decision.message)


def receipt_received(payment):
    dues = payment.dues
    ctx = context_for(dues.member, "fa", dues=dues)
    ctx["message"] = payment.payer_note
    return send("dues_receipt_staff", recipients_for("secretariat"), "fa", ctx)


def payment_reviewed(payment):
    event = "dues_confirmed" if payment.status == payment.Status.CONFIRMED else "dues_rejected"
    return to_member(payment.dues.member, event, dues=payment.dues, message=payment.staff_message)


def decision_made(decision, message_en=""):
    member = decision.member
    lang = member_language(member)
    message = message_en if (lang == "en" and message_en) else decision.message
    if decision.kind == "warning" and decision.reason == "dues" and decision.dues_id:
        return dues_warning(decision.dues, decision)
    return send(f"standing_{decision.kind}", member_recipients(member), lang,
                context_for(member, lang, decision=decision, message=message))


def staff_digest(role, lines):
    if not lines:
        return False
    ctx = {"list": "\n".join(lines), "admin_url": admin_url(), "site_name": SiteSettings.load().site_name}
    return send("standing_digest", recipients_for(role), "fa", ctx)
