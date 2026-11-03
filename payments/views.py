from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import translation
from django.views.decorators.csrf import csrf_exempt

from .gateways import TestGateway
from .models import Payment
from .services import complete


def _back(payment, ok):
    sep = "&" if "?" in payment.return_url else "?"
    return redirect(f"{payment.return_url}{sep}payment={'ok' if ok else 'failed'}")


@csrf_exempt  # the bank posts back here (IDPay) or redirects with GET (Zarinpal)
def callback(request, uid):
    payment = get_object_or_404(Payment, uid=uid)
    params = request.POST if request.method == "POST" else request.GET
    payment = complete(payment, params)
    return _back(payment, payment.is_paid)


def test_gateway(request, uid):
    """The page of the test gateway: a pretend bank with "pay" and "cancel"."""
    payment = get_object_or_404(Payment, uid=uid, provider="test", status=Payment.Status.STARTED)
    if not TestGateway.allowed():
        return redirect(payment.return_url)
    with translation.override(payment.language):
        return TemplateResponse(request, "payments/test_gateway.html", {"payment": payment})
