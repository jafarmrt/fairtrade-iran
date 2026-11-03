"""Copy the default SMS texts into editable templates. Never overwrites edits."""

from .models import SmsTemplate
from .registry import EVENTS


def ensure_sms_templates(stdout=None):
    created = 0
    for event in EVENTS.values():
        _, new = SmsTemplate.objects.get_or_create(
            event=event.key, defaults={"text": event.text, "text_en": event.text_en, "active": event.active},
        )
        created += new
    if stdout and created:
        stdout.write(f"Created {created} SMS template(s).")
