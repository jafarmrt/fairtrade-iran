"""
Simple request limits against password guessing and form spam.

Counts live in Django's cache. Production uses a file-based cache so all
gunicorn workers of the container share the counts (see settings).
Limits can be tuned with the THROTTLE_LIMITS setting, e.g.
THROTTLE_LIMITS = {"login_ip": (40, 900)}.
"""

import hashlib

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.dispatch import receiver
from django.template.response import TemplateResponse

# scope: (how many, in how many seconds)
DEFAULT_LIMITS = {
    "login_ip": (20, 15 * 60),         # failed sign-ins from one address
    "login_user": (10, 15 * 60),       # failed sign-ins for one username / e-mail
    "password_reset": (5, 60 * 60),    # reset e-mails asked from one address
    "lookup": (20, 60 * 60),           # order / application look-ups from one address
    "contact": (10, 60 * 60),          # contact form messages
    "complaint": (10, 60 * 60),        # confidential complaints
    "apply": (5, 60 * 60),             # membership applications
    "checkout": (10, 60 * 60),         # orders placed
    "two_factor_send": (8, 60 * 60),   # sign-in codes e-mailed to one user
}


def limit_for(scope):
    return {**DEFAULT_LIMITS, **getattr(settings, "THROTTLE_LIMITS", {})}[scope]


def client_ip(request):
    """The visitor's address. nginx appends the address it saw to X-Forwarded-For, so the last entry is trusted."""
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def _key(scope, value):
    digest = hashlib.sha256(f"{scope}:{value}".encode()).hexdigest()[:32]
    return f"throttle:{scope}:{digest}"


def count(scope, value):
    return cache.get(_key(scope, value), 0) if value else 0


def blocked(scope, value):
    return bool(value) and count(scope, value) >= limit_for(scope)[0]


def add(scope, value):
    """Count one more event; the window starts at the first event."""
    if not value:
        return 0
    key, window = _key(scope, value), limit_for(scope)[1]
    if cache.add(key, 1, window):
        return 1
    try:
        return cache.incr(key)
    except ValueError:  # expired between add() and incr()
        cache.set(key, 1, window)
        return 1


def reset(scope, value):
    if value:
        cache.delete(_key(scope, value))


def hit(request, scope):
    """Count this request; True when the address has gone over the limit for this scope."""
    ip = client_ip(request)
    if blocked(scope, ip):
        return True
    add(scope, ip)
    return False


def throttled_response(request):
    """A friendly "please try later" page with HTTP 429."""
    response = TemplateResponse(request, "core/throttled.html", {}, status=429)
    response["Retry-After"] = str(limit_for("contact")[1])
    response["Cache-Control"] = "no-store"
    return response


# ---- sign-in ----

def _username(credentials):
    return (credentials.get("username") or credentials.get("email") or "").strip().lower()


class ThrottleBackend:
    """
    First in AUTHENTICATION_BACKENDS. Stops authentication (for every backend)
    once an address or a username has too many failed sign-ins in a row.
    """

    def authenticate(self, request, username=None, **kwargs):
        name = (username or kwargs.get("email") or "").strip().lower()
        if blocked("login_user", name) or blocked("login_ip", client_ip(request)):
            raise PermissionDenied
        return None

    def get_user(self, user_id):
        # Being first in the list, this backend's path is stored for force_login()
        # sessions (tests, admin tools), so it must be able to load users.
        return ModelBackend().get_user(user_id)


@receiver(user_login_failed)
def _login_failed(sender, credentials, request=None, **kwargs):
    add("login_user", _username(credentials))
    add("login_ip", client_ip(request))


@receiver(user_logged_in)
def _logged_in(sender, request, user, **kwargs):
    reset("login_user", (user.get_username() or "").lower())
    if user.email:
        reset("login_user", user.email.lower())
