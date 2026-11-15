"""Rights for wholesale enquiries; called by seed_content. The page text is in content/pages/. Idempotent."""

from django.contrib.auth.models import Group, Permission

from home.management.commands import seed_data

INQUIRY_PERMS = ["view_wholesaleinquiry", "change_wholesaleinquiry", "add_wholesaleinquiry"]
HANDLER_GROUPS = [seed_data.SECRETARIAT, seed_data.MARKET]


def ensure_wholesale(command):
    """Admin rights for wholesale enquiries. The page itself is in content/pages/."""
    perms = list(Permission.objects.filter(content_type__app_label="wholesale", codename__in=INQUIRY_PERMS))
    settings_perm = Permission.objects.filter(content_type__app_label="wholesale",
                                              codename="change_wholesalesettings").first()
    for name in HANDLER_GROUPS:
        group = Group.objects.filter(name=name).first()
        if group is None:
            continue
        group.permissions.add(*perms)
        if settings_perm is not None:
            group.permissions.add(settings_perm)
