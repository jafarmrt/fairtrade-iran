"""
Two-step sign-in for staff: after the password, a one-time code sent by e-mail.

Who needs it, how long a code lasts and how long a browser is remembered are
set in the admin (Settings > امنیت). The check runs as middleware, so it covers
every way of signing in (Wagtail admin, member panel). If the site's e-mail
breaks and nobody can get in, set TWO_FACTOR_DISABLED=1 on the server for a
moment, sign in, and fix the e-mail settings.
"""

import secrets
import time

from django.conf import settings
from django.contrib.auth import logout
from django.core.mail import send_mail
from django.core.signing import BadSignature
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache

from . import throttle
from .models import SecuritySettings, SiteSettings, is_english

SESSION_OK = "two_factor_user"
SESSION_CODE = "two_factor_code"
COOKIE = "ft_trusted"
COOKIE_SALT = "core.two_factor.trusted"
MAX_ATTEMPTS = 5
RESEND_SECONDS = 60
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
EXEMPT_PREFIXES = ("/static/", "/media/", "/two-factor/", "/admin/logout/", "/pay/", "/robots.txt", "/favicon.ico")


def t(fa, en):
    return en if is_english() else fa


def is_required(user, config=None):
    if not user.is_authenticated or getattr(settings, "TWO_FACTOR_DISABLED", False):
        return False
    config = config or SecuritySettings.load()
    if config.two_factor == SecuritySettings.TwoFactor.SUPERUSERS:
        return user.is_superuser
    if config.two_factor == SecuritySettings.TwoFactor.STAFF:
        return user.is_superuser or user.has_perm("wagtailadmin.access_admin")
    return False


def is_verified(request):
    return request.session.get(SESSION_OK) == request.user.pk


# ---- remembered browsers ----

def _device_token(user):
    # Changes when the password changes, so a new password forgets every remembered browser.
    return salted_hmac(COOKIE_SALT, f"{user.pk}:{user.password}").hexdigest()[:40]


def remember_browser(response, user, days):
    response.set_signed_cookie(COOKIE, f"{user.pk}:{_device_token(user)}", salt=COOKIE_SALT,
                               max_age=days * 86400, httponly=True, samesite="Lax",
                               secure=getattr(settings, "SESSION_COOKIE_SECURE", False))


def trusted_browser(request, days):
    if not days:
        return False
    try:
        value = request.get_signed_cookie(COOKIE, salt=COOKIE_SALT, max_age=days * 86400)
    except (KeyError, BadSignature):
        return False
    return constant_time_compare(value, f"{request.user.pk}:{_device_token(request.user)}")


# ---- middleware ----

class TwoFactorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (user is not None and user.is_authenticated and not request.path.startswith(EXEMPT_PREFIXES)
                and not request.path.endswith("/panel/logout/") and not is_verified(request)):
            config = SecuritySettings.load(request_or_site=request)
            if is_required(user, config):
                if trusted_browser(request, config.two_factor_remember_days):
                    request.session[SESSION_OK] = user.pk
                else:
                    target = request.get_full_path() if request.method == "GET" else "/admin/"
                    return redirect(f"{reverse('two_factor')}?next={target}")
        return self.get_response(request)


# ---- the code page ----

def _hash(user, code):
    return salted_hmac("core.two_factor.code", f"{user.pk}:{code}").hexdigest()


def send_code(request, config):
    user = request.user
    if not user.email:
        return False
    if throttle.blocked("two_factor_send", str(user.pk)):
        return False
    throttle.add("two_factor_send", str(user.pk))
    code = f"{secrets.randbelow(10**6):06d}"
    request.session[SESSION_CODE] = {
        "hash": _hash(user, code), "expires": time.time() + config.two_factor_code_minutes * 60,
        "attempts": 0, "sent": time.time(),
    }
    site = SiteSettings.load().site_name
    minutes = config.two_factor_code_minutes
    subject = t(f"کد ورود {site}: {code}", f"Your sign-in code for {site}: {code}")
    body = t(
        f"کد ورود شما: {code}\n\nاین کد تا {minutes} دقیقه معتبر است. اگر شما وارد نشده‌اید، "
        "همین حالا رمز عبور خود را عوض کنید و به مدیر سایت خبر دهید.",
        f"Your sign-in code: {code}\n\nIt is valid for {minutes} minutes. If you did not just sign in, "
        "change your password now and tell the site administrator.",
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    return True


def _next_url(request):
    target = request.POST.get("next") or request.GET.get("next") or "/admin/"
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        target = "/admin/"
    return target


def _masked(email):
    name, _, domain = email.partition("@")
    return (name[:2] + "•" * max(len(name) - 2, 1)) + "@" + domain


@never_cache
def verify(request):
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    config = SecuritySettings.load(request_or_site=request)
    target = _next_url(request)
    if is_verified(request) or not is_required(request.user, config):
        return redirect(target)

    error, info = "", ""
    state = request.session.get(SESSION_CODE)
    if request.method == "POST" and request.POST.get("action") == "logout":
        logout(request)
        return redirect(settings.LOGIN_URL)
    if request.method == "POST" and request.POST.get("action") == "resend":
        if state and time.time() - state.get("sent", 0) < RESEND_SECONDS:
            error = t("کمی صبر کنید و دوباره درخواست کد بدهید.", "Please wait a moment before asking for a new code.")
        elif send_code(request, config):
            info = t("کد تازه فرستاده شد.", "A new code has been sent.")
        else:
            error = t("فرستادن کد ممکن نشد. کمی بعد دوباره بکوشید یا با مدیر سایت تماس بگیرید.",
                      "The code could not be sent. Please try again later or contact the site administrator.")
    elif request.method == "POST":
        code = "".join(ch for ch in request.POST.get("code", "").translate(DIGITS) if ch in "0123456789")
        if not state or time.time() > state["expires"] or state["attempts"] >= MAX_ATTEMPTS:
            request.session.pop(SESSION_CODE, None)
            error = t("کد منقضی شده است؛ «فرستادن کد تازه» را بزنید.", "This code has expired. Please ask for a new one.")
        elif constant_time_compare(_hash(request.user, code), state["hash"]):
            request.session.pop(SESSION_CODE, None)
            request.session.cycle_key()
            request.session[SESSION_OK] = request.user.pk
            response = redirect(target)
            if request.POST.get("remember") and config.two_factor_remember_days:
                remember_browser(response, request.user, config.two_factor_remember_days)
            return response
        else:
            state["attempts"] += 1
            request.session[SESSION_CODE] = state
            left = MAX_ATTEMPTS - state["attempts"]
            error = (t(f"کد درست نیست. {left} بار دیگر می‌توانید بکوشید.", f"That code is not right. {left} tries left.")
                     if left else t("کد درست نیست؛ «فرستادن کد تازه» را بزنید.",
                                    "That code is not right. Please ask for a new one."))
    elif not state or time.time() > state["expires"]:
        if not send_code(request, config) and not request.user.email:
            error = t("برای حساب شما ایمیلی ثبت نشده و کد ورود فرستاده نمی‌شود. با مدیر سایت تماس بگیرید.",
                      "Your account has no e-mail address, so no sign-in code can be sent. "
                      "Please contact the site administrator.")

    response = TemplateResponse(request, "core/two_factor.html", {
        "error": error, "info": info, "next": target,
        "email": _masked(request.user.email) if request.user.email else "",
        "remember_days": config.two_factor_remember_days,
        "minutes": config.two_factor_code_minutes,
    })
    response["Cache-Control"] = "no-store"
    return response
