"""
Keeps member profiles in step with the membership workflow, creates panel
accounts and sends the invitation e-mail.
"""

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from members.models import Member

logger = logging.getLogger(__name__)

MEMBERS_GROUP = "اعضا"  # created by seed_content (home/management/commands/seed_data.py)

# Membership file status -> member profile status
STATUS_MAP = {
    "trial": Member.TRIAL,
    "trial_extended": Member.TRIAL,
    "member": Member.OFFICIAL,
    "not_accepted": Member.SUSPENDED,
}


def add_to_members_group(users):
    group = Group.objects.filter(name=MEMBERS_GROUP).first()
    if group is not None:
        group.user_set.add(*users)


def _website(value):
    value = (value or "").strip()
    return value if value.startswith(("http://", "https://")) else ""


@transaction.atomic
def sync_profile(application, status):
    """Create or update the public profile of a membership file. Returns (member, created)."""
    from .models import PanelSettings

    target = STATUS_MAP.get(status)
    if target is None:
        return None, False
    settings = PanelSettings.load()
    member = Member.objects.filter(application=application).first()
    if member is None:
        if target == Member.SUSPENDED or (target == Member.TRIAL and not settings.create_profile_on_trial):
            return None, False
        member = Member(
            application=application,
            name=application.name,
            name_en=application.name_en,
            member_type=application.member_type,
            status=target,
            city=application.city,
            website_url=_website(application.website),
            joined_on=timezone.localdate(),
            is_published=settings.publish_new_profiles,
        )
        member.save()
        created = True
    else:
        member.status = target
        if target == Member.SUSPENDED:
            member.is_published = False
        member.save(update_fields=["status", "is_published", "updated_at"])
        created = False

    if settings.invite_new_members and target != Member.SUSPENDED and not member.managers.exists():
        user = ensure_user(application.email, application.contact_person or application.name)
        if user is not None:
            member.managers.add(user)
            lang = application.language if application.language in ("fa", "en") else "fa"
            transaction.on_commit(lambda: send_invite(user, member, lang))
    return member, created


def ensure_user(email, display_name=""):
    email = (email or "").strip().lower()
    if not email:
        return None
    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        username = email[:150]
        n = 2
        while User.objects.filter(username=username).exists():
            username = f"{email[:140]}-{n}"
            n += 1
        user = User(username=username, email=email, first_name=display_name[:150])
        user.set_unusable_password()
        user.save()
    return user


def panel_urls(user, lang):
    from membership.notifications import base_url

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    with translation.override(lang):
        set_password = reverse("panel:password_reset_confirm", kwargs={"uidb64": uid, "token": token})
        panel = reverse("panel:dashboard")
    return base_url() + set_password, base_url() + panel


def send_invite(user, member, lang="fa"):
    from core.models import SiteSettings
    from membership.notifications import send

    set_password_url, panel_url = panel_urls(user, lang)
    with translation.override(lang):
        context = {
            "name": member.tr("name"),
            "username": user.get_username(),
            "set_password_url": set_password_url,
            "panel_url": panel_url,
            "site_name": SiteSettings.load().tr("site_name"),
        }
    return send("panel_invite", [user.email], lang, context)


def notify_product_review(product):
    from core.models import SiteSettings
    from membership.notifications import base_url, send

    from .models import PanelSettings

    to = PanelSettings.load().review_email or SiteSettings.load().notification_email
    if not to:
        return False
    with translation.override("fa"):
        admin_url = base_url() + reverse("wagtailsnippets_products_product:edit", args=[product.pk])
        context = {
            "product": product.name,
            "member": product.member.name,
            "admin_url": admin_url,
            "site_name": SiteSettings.load().site_name,
        }
    return send("panel_product_review", [to], "fa", context)
