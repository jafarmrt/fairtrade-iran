"""
Settings and admin rights for the member directory and the shop, called from
`python manage.py seed_content`. The texts (members page, shop page, regions,
categories, founding members) are in the content package: content/members.yaml
and content/pages/.
"""

from django.contrib.auth.models import Group, Permission

from home.management.commands import seed_data

from .models import DirectorySettings

# Groups that may add and edit members, products, categories and regions in the admin panel.
EDITOR_GROUPS = [seed_data.SECRETARIAT, seed_data.PR]
EDIT_MODELS = [("members", "member"), ("members", "region"), ("products", "product"),
               ("products", "category"), ("products", "productimage")]
SETTINGS_MODELS = [("members", "directorysettings"), ("products", "shopsettings")]


def seed_directory(command):
    """Called by seed_content. The pages, regions, categories and founding members come from the
    content package (content/members.yaml, content/pages/); this only adds settings and rights."""
    from products.models import ShopSettings

    DirectorySettings.load()
    ShopSettings.load()
    _grant_permissions()


def _grant_permissions():
    perms = []
    for app_label, model in EDIT_MODELS:
        for action in ("add", "change", "delete"):
            perms.append(Permission.objects.get(content_type__app_label=app_label, codename=f"{action}_{model}"))
    for app_label, model in SETTINGS_MODELS:
        perms.append(Permission.objects.get(content_type__app_label=app_label, codename=f"change_{model}"))
    for name in EDITOR_GROUPS:
        group = Group.objects.filter(name=name).first()
        if group:
            group.permissions.add(*perms)
