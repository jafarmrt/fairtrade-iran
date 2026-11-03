"""
What can be paid online. Each purpose says how much is owed for an object,
whether it can be paid now, and what happens once the bank confirms it.
The other apps are imported lazily, so payments does not depend on them at
import time.
"""

from django.db import transaction
from django.utils import timezone

PURPOSES = {}


class Purpose:
    key = ""

    def amount(self, obj):
        raise NotImplementedError

    def can_pay(self, obj):
        return bool(self.amount(obj))

    def description(self, obj):
        return ""

    def contact(self, obj):
        """(mobile, email) of the payer, passed to the gateway."""
        return "", ""

    def meta(self, obj):
        return {}

    def on_paid(self, payment, obj):
        raise NotImplementedError


def register(cls):
    PURPOSES[cls.key] = cls()
    return cls


def get(key):
    return PURPOSES[key]


@register
class ApplicationFee(Purpose):
    key = "application_fee"

    def amount(self, application):
        return application.fee_amount or 0

    def can_pay(self, application):
        return application.fee_required and not application.fee_confirmed and not application.is_closed

    def description(self, application):
        return f"هزینه درخواست عضویت {application.tracking_code}"

    def contact(self, application):
        return application.phone, application.email

    def on_paid(self, payment, application):
        from membership.models import ApplicationEvent

        if application.fee_confirmed:
            return
        application.fee_confirmed_at = timezone.now()
        application.payment_reference = f"{payment.ref_id} (آنلاین)"
        application.save(update_fields=["fee_confirmed_at", "payment_reference", "updated_at"])
        ApplicationEvent.objects.create(
            application=application, action="fee_paid_online",
            internal_note=f"هزینه درخواست آنلاین پرداخت شد؛ شماره پیگیری {payment.ref_id}، مبلغ {payment.amount} ریال",
        )


@register
class AnnualDues(Purpose):
    key = "dues"

    def amount(self, dues):
        return dues.amount

    def can_pay(self, dues):
        return dues.can_pay and dues.amount > 0

    def description(self, dues):
        return f"حق عضویت سال {dues.year} - {dues.member.name}"

    def contact(self, dues):
        from standing.notifications import member_phone, member_recipients

        emails = member_recipients(dues.member)
        return member_phone(dues.member), emails[0] if emails else ""

    def on_paid(self, payment, dues):
        from standing.models import Dues, DuesPayment
        from standing.services import review_payment

        dues = Dues.objects.select_for_update().get(pk=dues.pk)
        if dues.status in (Dues.Status.PAID, Dues.Status.WAIVED):
            return  # already settled another way; the payment stays on record for the secretariat
        record = DuesPayment.objects.create(
            dues=dues, amount=payment.amount, reference=payment.ref_id, payer_note="پرداخت آنلاین",
            paid_on_text=timezone.localdate().isoformat(), status=DuesPayment.Status.PENDING,
        )
        review_payment(record, None, confirm=True, message="")


@register
class Order(Purpose):
    """A buyer's checkout: pays all its orders whose money goes to the House."""

    key = "order"

    def amount(self, purchase):
        return sum(o.total for o in purchase.orders_payable_online())

    def description(self, purchase):
        return f"سفارش {purchase.code}"

    def contact(self, purchase):
        return purchase.phone, purchase.email

    def meta(self, purchase):
        return {"orders": [o.pk for o in purchase.orders_payable_online()]}

    def on_paid(self, payment, purchase):
        from shop.services import paid_online

        paid_online(purchase, payment)


def run_on_paid(payment):
    obj = payment.target
    if obj is None:
        return
    with transaction.atomic():
        get(payment.purpose).on_paid(payment, obj)
