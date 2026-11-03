"""
Content-Security-Policy for the public site and the member panel.

Our own inline scripts carry a per-request nonce ({{ CSP_NONCE }}). The
analytics and trust-badge code that staff paste in the admin gets the nonce
added automatically, and the origins it loads from are allowed, so pasting
an Umami or eNamad snippet keeps working without editing the policy.
The Wagtail admin is left alone: it has its own inline scripts.
"""

import re
import secrets
from urllib.parse import urlsplit

SKIP_PREFIXES = ("/admin/", "/django-admin/", "/static/", "/media/")
URL_IN_CODE = re.compile(r"""(?:src|href|action)\s*=\s*["']?(https://[^"'\s>]+)""", re.I)
SCRIPT_TAG = re.compile(r"<script(?![^>]*\bnonce\s*=)", re.I)


def origin(url):
    """https://host[:port] of a URL, or "" if it is not an https URL."""
    url = (url or "").strip()
    if not url.lower().startswith("https://"):
        return ""
    parts = urlsplit(url)
    if not parts.hostname or not re.fullmatch(r"[a-z0-9.*-]+", parts.hostname):
        return ""
    return f"https://{parts.hostname}" + (f":{parts.port}" if parts.port else "")


def origins_in(code):
    return {o for o in (origin(u) for u in URL_IN_CODE.findall(code or "")) if o}


def add_nonce(code, nonce):
    """Give every <script> in admin-entered code the page's nonce."""
    if not code or not nonce:
        return code
    return SCRIPT_TAG.sub(f'<script nonce="{nonce}"', code)


def gateway_origins():
    from payments.gateways import GATEWAYS

    hosts = set()
    for gateway in GATEWAYS.values():
        hosts.update(getattr(gateway, "redirect_origins", ()))
    return hosts


def build_policy(nonce, security, seo):
    third_party = origins_in(seo.head_code) | origins_in(seo.footer_badges) | set(security.extra_sources())
    extra = " ".join(sorted(third_party))
    forms = " ".join(sorted(gateway_origins() | third_party))
    directives = [
        "default-src 'self'",
        f"script-src 'self' 'nonce-{nonce}' {extra}",
        f"style-src 'self' 'unsafe-inline' {extra}",
        "img-src 'self' data: https:",
        f"font-src 'self' data: {extra}",
        f"connect-src 'self' {extra}",
        "frame-src 'self' https:",          # videos and maps embedded by editors
        "media-src 'self' https:",
        "object-src 'none'",
        "base-uri 'self'",
        f"form-action 'self' {forms}",       # payment forms are redirected to the bank
        "frame-ancestors 'self'",
    ]
    return "; ".join(" ".join(d.split()) for d in directives)


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        if request.path.startswith(SKIP_PREFIXES) or "Content-Security-Policy" in response:
            return response
        if not response.get("Content-Type", "").startswith("text/html"):
            return response
        from .models import SecuritySettings, SeoSettings

        security = SecuritySettings.load(request_or_site=request)
        if security.csp_mode == SecuritySettings.CspMode.OFF:
            return response
        header = ("Content-Security-Policy" if security.csp_mode == SecuritySettings.CspMode.ENFORCE
                  else "Content-Security-Policy-Report-Only")
        response[header] = build_policy(request.csp_nonce, security, SeoSettings.load(request_or_site=request))
        return response
