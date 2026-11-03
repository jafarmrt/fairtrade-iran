import logging

from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from members.models import Member
from membership.workflow import status_entered

from .onboarding import add_to_members_group, sync_profile

logger = logging.getLogger(__name__)


@receiver(status_entered, dispatch_uid="memberpanel_sync_profile")
def on_status_entered(sender, application, status, **kwargs):
    try:
        sync_profile(application, status)
    except Exception:  # a profile problem must never block the membership workflow
        logger.exception("Could not sync the member profile of application %s", application.pk)


@receiver(m2m_changed, sender=Member.managers.through, dispatch_uid="memberpanel_managers_group")
def on_managers_changed(sender, instance, action, reverse, pk_set, **kwargs):
    """People who manage a member get the members' group (member-only documents)."""
    if action != "post_add" or not pk_set:
        return
    from django.contrib.auth import get_user_model

    if reverse:
        users = [instance]
    else:
        users = list(get_user_model().objects.filter(pk__in=pk_set))
    add_to_members_group(users)
