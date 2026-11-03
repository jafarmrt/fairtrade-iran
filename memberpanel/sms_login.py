"""
Member panel sign-in with a one-time SMS code, and a page where a signed-in
member sets (and confirms) the mobile they sign in with.

On only when PanelSettings.sms_login and SmsSettings.enabled are both on.
The code is kept hashed in the session with an expiry and a try counter;
sending is limited per mobile and per address (core.throttle). The page says
the same thing whether or not the number is registered, so it does not reveal
who is a member. Staff who must use two-step sign-in still get the e-mail code
afterwards (core.two_factor middleware).
"""

import secrets
import time

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache

from core import throttle
from core.iran import clean_mobile, only_digits
from core.models import SiteSettings, is_english
from sms.models import SmsSettings
from sms.service import render, send_text

from .models import LoginMobile, PanelSettings

SESSION_LOGIN = "panel_sms_login"
SESSION_VERIFY = "panel_sms_verify"
MAX_ATTEMPTS = 5
RESEND_SECONDS = 60
BACKEND = "django.contrib.auth.backends.ModelBackend"


def t(fa, en):
    return en if is_english() else fa


def enabled(request=None):
    return (PanelSettings.load(request_or_site=request).sms_login
            and SmsSettings.load(request_or_site=request).enabled)


def _hash(mobile, code):
    return salted_hmac("memberpanel.sms_login", f"{mobile}:{code}").hexdigest()


def _masked(mobile):
    return f"{mobile[:4]}•••{mobile[-4:]}" if len(mobile) == 11 else mobile


def send_code(request, key, mobile):
    """Send a fresh code to `mobile` and keep its hash under session[key]. False if limited or not sent."""
    ip = throttle.client_ip(request)
    if throttle.blocked("sms_code_mobile", mobile) or throttle.blocked("sms_code_ip", ip):
        return False
    throttle.add("sms_code_mobile", mobile)
    throttle.add("sms_code_ip", ip)
    minutes = PanelSettings.load(request_or_site=request).sms_code_minutes or 5
    code = f"{secrets.randbelow(10**6):06d}"
    lang = "en" if is_english() else "fa"
    text = render("panel_login_code", lang, {
        "code": code, "minutes": minutes, "site_name": SiteSettings.load(request_or_site=request).tr("site_name")})
    if not text:
        return False
    request.session[key] = {"mobile": mobile, "hash": _hash(mobile, code), "expires": time.time() + minutes * 60,
                            "attempts": 0, "sent": time.time()}
    return send_text([mobile], text, event="panel_login_code") > 0


def check_code(request, key, code):
    """'' when right (and the state is cleared), else an error message."""
    state = request.session.get(key)
    code = only_digits(code)
    if not state or time.time() > state["expires"] or state["attempts"] >= MAX_ATTEMPTS:
        request.session.pop(key, None)
        return t("کد منقضی شده است؛ دوباره درخواست کد بدهید.", "This code has expired. Please ask for a new one.")
    if constant_time_compare(_hash(state["mobile"], code), state["hash"]):
        request.session.pop(key, None)
        return ""
    state["attempts"] += 1
    request.session[key] = state
    left = MAX_ATTEMPTS - state["attempts"]
    if left:
        return t(f"کد درست نیست. {left} بار دیگر می‌توانید بکوشید.", f"That code is not right. {left} tries left.")
    request.session.pop(key, None)
    return t("کد درست نیست؛ دوباره درخواست کد بدهید.", "That code is not right. Please ask for a new one.")


def _next(request):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                  require_https=request.is_secure()):
        return target
    return reverse("panel:dashboard")


@never_cache
def login_view(request):
    if not PanelSettings.load(request_or_site=request).enabled:
        return TemplateResponse(request, "memberpanel/closed.html", status=503)
    if not enabled(request):
        return redirect("panel:login")
    if request.user.is_authenticated:
        return redirect(_next(request))
    error, mobile = "", ""
    state = request.session.get(SESSION_LOGIN)
    step = request.POST.get("step") if request.method == "POST" else ""
    if step == "send":
        mobile = request.POST.get("mobile", "")
        try:
            mobile = clean_mobile(mobile, english=is_english())
        except ValidationError as e:
            error = e.messages[0]
        if mobile and not error:
            if state and state.get("mobile") == mobile and time.time() - state.get("sent", 0) < RESEND_SECONDS:
                error = t("کمی صبر کنید و دوباره درخواست کد بدهید.", "Please wait a moment before asking for a new code.")
            elif throttle.blocked("sms_code_mobile", mobile) or throttle.blocked("sms_code_ip",
                                                                                 throttle.client_ip(request)):
                error = t("درخواست کد بیش از اندازه بوده است؛ یک ساعت دیگر دوباره بکوشید یا با رمز عبور وارد شوید.",
                          "Too many codes were asked for. Please try again in an hour, or sign in with your password.")
            else:
                entry = LoginMobile.objects.select_related("user").filter(mobile=mobile, user__is_active=True).first()
                if entry is not None:
                    send_code(request, SESSION_LOGIN, mobile)
                else:
                    # Same answer as for a registered number; count it, so numbers cannot be probed quickly.
                    throttle.add("sms_code_ip", throttle.client_ip(request))
                    request.session[SESSION_LOGIN] = {"mobile": mobile, "hash": "", "expires": time.time() + 300,
                                                      "attempts": 0, "sent": time.time()}
                return redirect(f"{reverse('panel:sms_login')}?next={_next(request)}")
    elif step == "verify" and state:
        error = check_code(request, SESSION_LOGIN, request.POST.get("code", ""))
        if not error:
            entry = LoginMobile.objects.select_related("user").filter(mobile=state["mobile"],
                                                                      user__is_active=True).first()
            if entry is None:
                error = t("ورود ممکن نشد.", "Sign-in failed.")
            else:
                login(request, entry.user, backend=BACKEND)
                if entry.verified_at is None:
                    LoginMobile.objects.filter(pk=entry.pk).update(verified_at=timezone.now())
                return redirect(_next(request))
    elif step == "restart":
        request.session.pop(SESSION_LOGIN, None)
        return redirect(f"{reverse('panel:sms_login')}?next={_next(request)}")
    state = request.session.get(SESSION_LOGIN)
    if state and time.time() > state["expires"]:
        request.session.pop(SESSION_LOGIN, None)
        state = None
    response = TemplateResponse(request, "memberpanel/registration/sms_login.html", {
        "error": error,
        "mobile": mobile if isinstance(mobile, str) else "",
        "sent_to": _masked(state["mobile"]) if state else "",
        "next": _next(request),
    })
    response["Cache-Control"] = "no-store"
    return response


@never_cache
@login_required(login_url="panel:login")
def mobile_view(request):
    """The signed-in user sets the mobile they sign in with, confirming it with a code."""
    entry = LoginMobile.objects.filter(user=request.user).first()
    error = ""
    state = request.session.get(SESSION_VERIFY)
    step = request.POST.get("step") if request.method == "POST" else ""
    sms_on = SmsSettings.load(request_or_site=request).enabled
    if step == "send" and sms_on:
        try:
            mobile = clean_mobile(request.POST.get("mobile", ""), english=is_english())
        except ValidationError as e:
            mobile, error = "", e.messages[0]
        if not mobile and not error:
            error = t("شماره موبایل را بنویسید.", "Please enter a mobile number.")
        elif mobile and LoginMobile.objects.filter(mobile=mobile).exclude(user=request.user).exists():
            error = t("این شماره برای حساب دیگری ثبت شده است. اگر شماره شماست، با دبیرخانه تماس بگیرید.",
                      "This number belongs to another account. If it is yours, please contact the secretariat.")
        elif mobile:
            if not send_code(request, SESSION_VERIFY, mobile):
                error = t("فرستادن کد ممکن نشد؛ کمی بعد دوباره بکوشید.", "The code could not be sent. Please try later.")
            return redirect("panel:mobile") if not error else _render_mobile(request, entry, error)
    elif step == "verify" and state:
        error = check_code(request, SESSION_VERIFY, request.POST.get("code", ""))
        if not error:
            mobile = state["mobile"]
            if LoginMobile.objects.filter(mobile=mobile).exclude(user=request.user).exists():
                error = t("این شماره برای حساب دیگری ثبت شده است.", "This number belongs to another account.")
            else:
                LoginMobile.objects.update_or_create(user=request.user,
                                                     defaults={"mobile": mobile, "verified_at": timezone.now()})
                messages.success(request, t("شماره موبایل ورود ذخیره شد.", "Your sign-in mobile was saved."))
                return redirect("panel:mobile")
    elif step == "remove" and entry is not None:
        entry.delete()
        messages.success(request, t("شماره موبایل ورود حذف شد.", "Your sign-in mobile was removed."))
        return redirect("panel:mobile")
    elif step == "restart":
        request.session.pop(SESSION_VERIFY, None)
        return redirect("panel:mobile")
    return _render_mobile(request, entry, error)


def _render_mobile(request, entry, error):
    from .views import render as panel_render

    state = request.session.get(SESSION_VERIFY)
    if state and time.time() > state["expires"]:
        request.session.pop(SESSION_VERIFY, None)
        state = None
    return panel_render(request, "memberpanel/mobile.html", {
        "entry": entry,
        "error": error,
        "pending": _masked(state["mobile"]) if state else "",
        "sms_on": SmsSettings.load(request_or_site=request).enabled,
        "sms_login": enabled(request),
        "current": "mobile",
    })
