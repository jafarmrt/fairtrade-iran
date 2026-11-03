"""
The list of events that can send an SMS. Apps add theirs from an
`sms_events.py` module (discovered at start-up), so each app owns its texts.
The default text is copied into an SmsTemplate by seed_content, where staff
edit it, and is the fallback when that template is missing.
"""

from dataclasses import dataclass

AUDIENCES = {
    "applicant": "متقاضی یا عضو",
    "secretariat": "دبیرخانه",
    "commission": "کمیسیون نظارتی",
}


@dataclass(frozen=True)
class SmsEvent:
    key: str
    label: str
    text: str
    text_en: str = ""
    audience: str = "applicant"
    active: bool = True


EVENTS = {}


def register(key, label, text, text_en="", audience="applicant", active=True):
    EVENTS[key] = SmsEvent(key, label, text, text_en, audience, active)
    return EVENTS[key]


def get(key):
    return EVENTS.get(key)


def event_choices():
    """Used as the (callable) choices of SmsTemplate.event, so new events need no migration."""
    return [(e.key, e.label) for e in sorted(EVENTS.values(), key=lambda e: e.key)]
