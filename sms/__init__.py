"""
SMS notifications, next to the existing e-mails.

Other apps call the two helpers below; both never raise and return how many
messages were handed to the provider. Texts, provider, API key, sender line
and staff numbers are all edited in the admin panel (Settings > پیامک and the
"پیامک" menu). Nothing is sent until SMS is switched on there.

    from sms import notify, notify_role

    notify("membership_received", application.phone, context, lang="fa")
    notify_role("membership_staff_new", "secretariat", context)

Describe a new event in your app's `sms_events.py`:

    from sms.registry import register
    register("fees_due", "به عضو: یادآوری حق عضویت", "{name} گرامی، ...", "Dear {name}, ...")
"""


def notify(event, to, context=None, lang="fa"):
    from .service import notify as _notify

    return _notify(event, to, context, lang)


def notify_role(event, role, context=None, lang="fa"):
    from .service import notify_role as _notify_role

    return _notify_role(event, role, context, lang)
