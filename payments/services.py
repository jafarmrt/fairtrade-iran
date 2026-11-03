import logging

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from core.models import is_english

from . import purposes
from .gateways import GatewayError, get_gateway
from .models import Payment, PaymentSettings

logger = logging.getLogger(__name__)


def online_enabled(purpose):
    return PaymentSettings.load().enabled_for(purpose)


def callback_url(request, payment):
    return request.build_absolute_uri(reverse("payments:callback", args=[payment.uid]))


def start_payment(request, purpose_key, obj, return_url):
    """
    Create a Payment and send the buyer to the gateway. On any problem, show a
    message and go back to return_url, where the receipt upload is still there.
    """
    config = PaymentSettings.load()
    purpose = purposes.get(purpose_key)
    english = is_english()
    if not config.enabled_for(purpose_key) or not purpose.can_pay(obj):
        messages.error(request, "Online payment is not available for this." if english
                       else "پرداخت آنلاین برای این مورد در دسترس نیست.")
        return redirect(return_url)
    mobile, email = purpose.contact(obj)
    payment = Payment.objects.create(
        purpose=purpose_key,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        meta=purpose.meta(obj),
        amount=purpose.amount(obj),
        description=purpose.description(obj)[:255],
        mobile=mobile or "",
        email=email or "",
        language="en" if english else "fa",
        return_url=return_url,
        provider=config.provider,
    )
    try:
        url = get_gateway(config).request(payment, callback_url(request, payment))
    except GatewayError as exc:
        logger.warning("Payment %s could not start: %s", payment.uid, exc)
        payment.status = Payment.Status.FAILED
        payment.error = str(exc)[:255]
        payment.save(update_fields=["status", "error"])
        messages.error(request, "The payment gateway is not available right now. Please try again later or "
                                "pay by bank transfer." if english else
                       "درگاه پرداخت الان در دسترس نیست. کمی بعد دوباره بکوشید یا از راه واریز به حساب بپردازید.")
        return redirect(return_url)
    payment.save(update_fields=["authority"])
    return redirect(url)


def complete(payment, params):
    """
    Verify a payment the buyer came back from. Safe to call twice: only the
    first successful verification settles the order, fee or dues.
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status != Payment.Status.STARTED:
            return payment
        try:
            result = get_gateway(PaymentSettings.load(), payment.provider).verify(payment, params)
        except GatewayError as exc:
            result = None
            payment.error = str(exc)[:255]
        if result is not None and result.ok:
            payment.status = Payment.Status.PAID
            payment.paid_at = timezone.now()
            payment.ref_id = result.ref_id[:100]
            payment.card = result.card[:40]
            payment.raw = result.raw
            payment.save()
            purposes.run_on_paid(payment)
        elif result is not None and not result.final:
            # Not the gateway's return for this payment: keep it open for the real one.
            payment.error = result.error[:255]
            payment.save(update_fields=["error"])
        elif result is not None:
            payment.status = Payment.Status.FAILED
            payment.error = result.error[:255]
            payment.raw = result.raw
            payment.save()
        else:
            # Could not reach the gateway to verify: leave it started, so a later
            # return (or the secretariat) can still settle it.
            payment.save(update_fields=["error"])
    return payment
