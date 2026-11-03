import logging

from core.templating import fill

from . import registry
from .backends import SmsError, get_backend
from .models import SmsLog, SmsSettings, SmsTemplate
from .phone import mobile_list

logger = logging.getLogger(__name__)


def render(event, lang, context):
    """The text for an event in a language, or None if that event is switched off."""
    template = SmsTemplate.objects.filter(event=event).first()
    if template is not None:
        if not template.active:
            return None
        text = template.text_en if (lang == "en" and template.text_en) else template.text
    else:
        default = registry.get(event)
        if default is None or not default.active:
            return None
        text = default.text_en if (lang == "en" and default.text_en) else default.text
    text = (text or "").strip()
    if not text:
        return None
    return fill(text, context or {})


def send_text(mobiles, text, event="", config=None):
    """Send a ready text. Logs every attempt; never raises. Returns the number of recipients."""
    config = config or SmsSettings.load()
    mobiles = mobile_list(mobiles)
    if not mobiles or not text:
        return 0
    backend = get_backend(config)
    error = ""
    try:
        backend.send(mobiles, text)
    except SmsError as exc:
        error = str(exc)
    except Exception as exc:  # an SMS problem must never break a form or a workflow step
        logger.exception("SMS backend failed for event %s", event)
        error = repr(exc)
    if error:
        logger.warning("SMS %s not sent: %s", event, error)
    try:
        SmsLog.objects.bulk_create([
            SmsLog(event=event, recipient=m, text=text, provider=backend.name, success=not error, error=error)
            for m in mobiles
        ])
    except Exception:
        logger.exception("Could not write SMS log")
    return 0 if error else len(mobiles)


def notify(event, to, context=None, lang="fa"):
    config = SmsSettings.load()
    if not config.enabled:
        return 0
    if isinstance(to, str):
        to = [to]
    mobiles = mobile_list(to)
    if not mobiles:
        return 0
    try:
        text = render(event, lang if lang in ("fa", "en") else "fa", context)
    except Exception:
        logger.exception("Could not render SMS %s", event)
        return 0
    if text is None:
        return 0
    return send_text(mobiles, text, event=event, config=config)


def notify_role(event, role, context=None, lang="fa"):
    config = SmsSettings.load()
    if not config.enabled:
        return 0
    return notify(event, config.mobiles_for(role), context, lang)
