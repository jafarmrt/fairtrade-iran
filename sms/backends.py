"""
SMS providers. Each backend gets the SmsSettings row and sends one text to a
list of mobiles. To add another Iranian provider, subclass BaseBackend,
add it to BACKENDS and to SmsSettings.Provider.

settings.SMS_BACKEND (a dotted path) overrides the provider chosen in the
admin: dev settings use the console backend, tests the locmem one, so a
development copy never spends real credit.
"""

import json
import logging
import sys
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)
TIMEOUT = 8

outbox = []  # filled by LocmemBackend, for tests


class SmsError(Exception):
    pass


class BaseBackend:
    name = ""

    def __init__(self, config):
        self.config = config

    def send(self, mobiles, text):
        """Send `text` to every number in `mobiles`; raise SmsError on failure."""
        raise NotImplementedError

    def require_credentials(self):
        if not self.config.effective_api_key:
            raise SmsError("کلید API سامانه پیامک وارد نشده است")
        if not self.config.sender:
            raise SmsError("شماره خط فرستنده وارد نشده است")

    def request(self, url, data=None, headers=None):
        req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise SmsError(f"HTTP {exc.code}: {body[:300]}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SmsError(f"اتصال به سامانه پیامک برقرار نشد: {exc}") from exc
        try:
            return json.loads(body)
        except ValueError as exc:
            raise SmsError(f"پاسخ نامعتبر از سامانه پیامک: {body[:300]}") from exc


class ConsoleBackend(BaseBackend):
    name = "console"

    def send(self, mobiles, text):
        sys.stdout.write(f"---- SMS to {', '.join(mobiles)} ----\n{text}\n--------\n")
        sys.stdout.flush()


class LocmemBackend(BaseBackend):
    name = "locmem"

    def send(self, mobiles, text):
        outbox.append({"to": list(mobiles), "text": text})


class KavenegarBackend(BaseBackend):
    """https://kavenegar.com/rest.html — sms/send"""

    name = "kavenegar"

    def send(self, mobiles, text):
        self.require_credentials()
        key = urllib.parse.quote(self.config.effective_api_key, safe="")
        data = urllib.parse.urlencode({
            "receptor": ",".join(mobiles), "sender": self.config.sender, "message": text,
        }).encode()
        result = self.request(f"https://api.kavenegar.com/v1/{key}/sms/send.json", data,
                              {"Content-Type": "application/x-www-form-urlencoded"})
        status = (result.get("return") or {}).get("status")
        if status != 200:
            raise SmsError(f"کاوه‌نگار: {(result.get('return') or {}).get('message', result)} ({status})")


class SmsIrBackend(BaseBackend):
    """https://app.sms.ir/developer/help — send/bulk"""

    name = "smsir"

    def send(self, mobiles, text):
        self.require_credentials()
        sender = self.config.sender
        payload = {
            "lineNumber": int(sender) if sender.isdigit() else sender,
            "messageText": text,
            "mobiles": list(mobiles),
        }
        result = self.request(
            "https://api.sms.ir/v1/send/bulk",
            json.dumps(payload).encode(),
            {"Content-Type": "application/json", "Accept": "application/json",
             "X-API-KEY": self.config.effective_api_key},
        )
        if result.get("status") != 1:
            raise SmsError(f"sms.ir: {result.get('message', result)} ({result.get('status')})")


BACKENDS = {
    "console": ConsoleBackend,
    "kavenegar": KavenegarBackend,
    "smsir": SmsIrBackend,
}


def get_backend(config):
    override = getattr(settings, "SMS_BACKEND", "")
    if override:
        return import_string(override)(config)
    return BACKENDS.get(config.provider, ConsoleBackend)(config)
