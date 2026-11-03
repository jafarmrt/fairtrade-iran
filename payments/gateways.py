"""
Gateway adapters. Each one sends the buyer to the bank page and verifies the
payment when the buyer comes back. Add a new Iranian gateway by subclassing
Gateway and adding it to GATEWAYS (and to PaymentSettings.Provider).

All amounts are in rials.
"""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


class GatewayError(Exception):
    pass


def post_json(url, payload, headers=None, timeout=20):
    """POST JSON and return (http status, decoded JSON). Raises GatewayError on network problems."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json", **(headers or {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, body = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GatewayError(f"اتصال به درگاه برقرار نشد: {exc}") from exc
    try:
        return status, json.loads(body or b"{}")
    except ValueError as exc:
        raise GatewayError(f"پاسخ نامعتبر از درگاه (HTTP {status})") from exc


class Verification:
    def __init__(self, ok, ref_id="", card="", error="", raw=None):
        self.ok, self.ref_id, self.card, self.error, self.raw = ok, ref_id, card, error, raw or {}


class Gateway:
    key = ""
    redirect_origins = ()  # where the buyer is sent; allowed in the site's Content-Security-Policy

    def __init__(self, config):
        self.config = config
        self.merchant_id = config.effective_merchant_id
        self.sandbox = config.sandbox

    def request(self, payment, callback_url):
        """Register the payment with the gateway; return the URL to send the buyer to."""
        raise NotImplementedError

    def verify(self, payment, params):
        """Check the payment after the buyer returns (params: GET/POST data). Returns a Verification."""
        raise NotImplementedError


class Zarinpal(Gateway):
    """Zarinpal REST API v4. https://www.zarinpal.com/docs/paymentGateway/"""

    key = "zarinpal"
    redirect_origins = ("https://payment.zarinpal.com", "https://sandbox.zarinpal.com")

    @property
    def host(self):
        return "https://sandbox.zarinpal.com" if self.sandbox else "https://payment.zarinpal.com"

    def request(self, payment, callback_url):
        metadata = {k: v for k, v in (("mobile", payment.mobile), ("email", payment.email)) if v}
        status, body = post_json(self.host + "/pg/v4/payment/request.json", {
            "merchant_id": self.merchant_id,
            "amount": payment.amount,
            "currency": "IRR",
            "description": payment.description or "پرداخت",
            "callback_url": callback_url,
            "metadata": metadata,
        })
        data = body.get("data") or {}
        if data.get("code") != 100 or not data.get("authority"):
            raise GatewayError(f"زرین‌پال درخواست را نپذیرفت: {body.get('errors') or body}")
        payment.authority = data["authority"]
        return f"{self.host}/pg/StartPay/{data['authority']}"

    def verify(self, payment, params):
        if params.get("Status") != "OK" or params.get("Authority") != payment.authority:
            return Verification(False, error="پرداخت انجام نشد یا لغو شد", raw=dict(params.items()))
        status, body = post_json(self.host + "/pg/v4/payment/verify.json", {
            "merchant_id": self.merchant_id, "amount": payment.amount, "authority": payment.authority,
        })
        data = body.get("data") or {}
        if data.get("code") in (100, 101):
            return Verification(True, ref_id=str(data.get("ref_id", "")), card=data.get("card_pan", ""), raw=body)
        return Verification(False, error=f"تأیید نشد: {body.get('errors') or data}", raw=body)


class Idpay(Gateway):
    """IDPay API v1.1. https://idpay.ir/web-service/v1.1/"""

    key = "idpay"
    redirect_origins = ("https://idpay.ir",)
    host = "https://api.idpay.ir/v1.1"

    @property
    def headers(self):
        return {"X-API-KEY": self.merchant_id, "X-SANDBOX": "1" if self.sandbox else "0"}

    def request(self, payment, callback_url):
        status, body = post_json(self.host + "/payment", {
            "order_id": str(payment.uid),
            "amount": payment.amount,
            "phone": payment.mobile,
            "mail": payment.email,
            "desc": payment.description,
            "callback": callback_url,
        }, self.headers)
        if status not in (200, 201) or not body.get("link"):
            raise GatewayError(f"آیدی‌پی درخواست را نپذیرفت: {body.get('error_message') or body}")
        payment.authority = body["id"]
        return body["link"]

    def verify(self, payment, params):
        if params.get("id") != payment.authority or params.get("order_id") != str(payment.uid):
            return Verification(False, error="پاسخ درگاه با این پرداخت نمی‌خواند", raw=dict(params.items()))
        if str(params.get("status")) != "10":
            return Verification(False, error="پرداخت انجام نشد یا لغو شد", raw=dict(params.items()))
        status, body = post_json(self.host + "/payment/verify",
                                 {"id": payment.authority, "order_id": str(payment.uid)}, self.headers)
        if str(body.get("status")) in ("100", "101", "200") and int(body.get("amount") or 0) == payment.amount:
            card = (body.get("payment") or {}).get("card_no", "")
            return Verification(True, ref_id=str(body.get("track_id", "")), card=card, raw=body)
        return Verification(False, error=f"تأیید نشد: {body.get('error_message') or body}", raw=body)


class TestGateway(Gateway):
    """
    A local page with "pay" and "cancel" buttons, to try the whole flow before
    the House has a real gateway. It only works when DEBUG is on or the server
    sets PAYMENT_ALLOW_TEST_GATEWAY=1, so it can never be used to "pay" for
    real on a live site by mistake.
    """

    key = "test"

    @staticmethod
    def allowed():
        return settings.DEBUG or getattr(settings, "PAYMENT_ALLOW_TEST_GATEWAY", False)

    def request(self, payment, callback_url):
        if not self.allowed():
            raise GatewayError("درگاه آزمایشی روی این سرور مجاز نیست؛ در تنظیمات پرداخت، درگاه واقعی را انتخاب کنید.")
        payment.authority = "TEST-" + payment.uid.hex[:12].upper()
        return reverse("payments:test_gateway", args=[payment.uid])

    def verify(self, payment, params):
        if not self.allowed():
            return Verification(False, error="درگاه آزمایشی مجاز نیست")
        if params.get("result") == "ok" and params.get("authority") == payment.authority:
            return Verification(True, ref_id="TEST" + payment.uid.hex[:8].upper(), card="6037-99**-****-1234",
                                raw={"test": True})
        return Verification(False, error="پرداخت آزمایشی لغو شد", raw={"test": True})


GATEWAYS = {g.key: g for g in (Zarinpal, Idpay, TestGateway)}


def get_gateway(config, provider=None):
    cls = GATEWAYS.get(provider or config.provider)
    if cls is None:
        raise GatewayError("درگاه پرداخت انتخاب‌شده شناخته نشد.")
    return cls(config)
