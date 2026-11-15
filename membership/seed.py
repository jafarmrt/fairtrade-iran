"""
Group permissions for membership files, called from `seed_content`. The
membership page, form questions, e-mail texts and certificate wording are in
the content package (content/pages/, content/membership-form.yaml,
content/emails.yaml, content/site.yaml).
"""

from django.contrib.auth.models import Group, Permission

from .email_defaults import DEFAULT_EMAILS
from .models import EmailTemplate


def ensure_membership(stdout=None):
    """E-mail texts the content package does not have (content/emails.yaml) come from email_defaults."""
    created = 0
    for event, (subject, body, subject_en, body_en) in DEFAULT_EMAILS.items():
        _, new = EmailTemplate.objects.get_or_create(
            event=event, defaults={"subject": subject, "body": body, "subject_en": subject_en, "body_en": body_en},
        )
        created += new
    if stdout and created:
        stdout.write(f"Created {created} e-mail template(s) from the built-in texts.")


def ensure_permissions(secretariat, commission, board):
    """Give the governance bodies their rights on membership files."""

    def perms(model, *codenames):
        return list(Permission.objects.filter(content_type__app_label="membership",
                                              content_type__model=model, codename__in=codenames))

    view = perms("membershipapplication", "view_membershipapplication")
    snippets = (perms("applicationquestion", "add_applicationquestion", "change_applicationquestion",
                      "delete_applicationquestion", "view_applicationquestion")
                + perms("emailtemplate", "add_emailtemplate", "change_emailtemplate", "view_emailtemplate")
                + perms("certificate", "change_certificate", "view_certificate"))
    dues = list(Permission.objects.filter(content_type__app_label="standing", codename__in=[
        "view_dues", "change_dues", "view_duespayment", "view_decision"]))
    for group, extra in (
        (secretariat, perms("membershipapplication", "secretariat_actions") + snippets + dues),
        (commission, perms("membershipapplication", "commission_actions") + perms("certificate", "view_certificate")),
        (board, perms("certificate", "view_certificate")),
    ):
        if isinstance(group, Group):
            group.permissions.add(*view, *extra)
