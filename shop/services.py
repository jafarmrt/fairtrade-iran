"""Everything that changes an order goes through here, so stock, history and notifications stay right."""

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from products.models import Product, ShopSettings

from . import notifications
from .models import Order, OrderEvent, OrderItem, Purchase, Seller


class OrderError(Exception):
    pass


BUYER, SELLER, STAFF, SYSTEM = "buyer", "seller", "staff", "system"


def log(order, action, by, user=None, message=""):
    return OrderEvent.objects.create(order=order, action=action, by=by, user=user, status=order.status,
                                     message=message)


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------


@transaction.atomic
def place_order(cart, buyer, language="fa", user=None):
    """
    Turn the cart into a Purchase with one Order per producer. Stock is checked
    again under a lock, so two buyers cannot take the last item together.
    Raises OrderError if something in the cart is no longer available.
    """
    shop = ShopSettings.load()
    ids = [int(k) for k in cart.data]
    locked = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=ids)}
    products = Product.visible().filter(pk__in=ids)
    groups = cart.groups(products)
    if not groups:
        raise OrderError("سبد خرید خالی است یا محصولات آن دیگر فروخته نمی‌شوند.")
    short = [line for group in groups for line in group.lines if line.reduced or line.quantity <= 0]
    if short:
        for line in short:  # fix the cart, so the next try goes through
            cart.set(line.product.pk, line.quantity)
        line = short[0]
        raise OrderError(f"از «{line.product.name}» فقط {line.quantity} عدد موجود است؛ سبد را به‌روز کردیم.")

    purchase = Purchase.objects.create(language=language, user=user if user and user.is_authenticated else None,
                                       **buyer)
    for group in groups:
        percent = group.seller.effective_commission(shop)
        order = Order.objects.create(
            purchase=purchase, member=group.member, payment_mode=group.seller.mode,
            subtotal=group.subtotal, shipping=group.shipping, total=group.total,
            commission_percent=percent, commission=Order.commission_for(group.subtotal, percent),
            shipping_method=group.option.name if group.option else "",
            shipping_method_en=group.option.name_en if group.option else "",
        )
        for line in group.lines:
            OrderItem.objects.create(order=order, product=line.product, name=line.product.name,
                                     name_en=line.product.name_en, unit_price=line.unit_price,
                                     quantity=line.quantity)
            _take_stock(locked[line.product.pk], line.quantity)
        log(order, "placed", BUYER)
    cart.clear()
    transaction.on_commit(lambda: notifications.placed(purchase))
    return purchase


def _take_stock(product, quantity):
    if product.stock_quantity is None:
        return
    product.stock_quantity = max(product.stock_quantity - quantity, 0)
    if product.stock_quantity == 0:
        product.in_stock = False
    product.save(update_fields=["stock_quantity", "in_stock", "updated_at"])


def _return_stock(order):
    for item in order.items.select_related("product"):
        product = item.product
        if product is None or product.stock_quantity is None:
            continue
        product = Product.objects.select_for_update().get(pk=product.pk)
        if product.stock_quantity == 0:
            product.in_stock = True
        product.stock_quantity += item.quantity
        product.save(update_fields=["stock_quantity", "in_stock", "updated_at"])


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------


@transaction.atomic
def submit_payment(order, reference="", note="", receipt=None):
    """The buyer says they paid by bank transfer: reference number and/or receipt photo."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in Order.OPEN:
        raise OrderError("پرداخت این سفارش پیش‌تر بررسی شده یا سفارش بسته است.")
    if not (reference.strip() or receipt):
        raise OrderError("شماره پیگیری یا تصویر رسید را بفرستید.")
    order.payment_reference = reference.strip()[:100]
    order.payer_note = note.strip()
    if receipt:
        order.receipt_name = receipt.name[:255]
        order.receipt = receipt
    order.status = Order.Status.PAYMENT_REVIEW
    order.save()
    log(order, "receipt", BUYER, message=note.strip())
    transaction.on_commit(lambda: notifications.receipt(order))
    return order


@transaction.atomic
def confirm_payment(order, user, by=STAFF, message=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in Order.OPEN:
        raise OrderError("این سفارش در انتظار پرداخت نیست.")
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save()
    log(order, "confirm_payment", by, user, message)
    transaction.on_commit(lambda: notifications.paid(order))
    return order


@transaction.atomic
def reject_payment(order, user, message, by=STAFF):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.PAYMENT_REVIEW:
        raise OrderError("رسیدی برای بررسی در این سفارش نیست.")
    if not message.strip():
        raise OrderError("بنویسید چرا پرداخت تأیید نشد؛ این پیام برای خریدار فرستاده می‌شود.")
    order.status = Order.Status.AWAITING_PAYMENT
    order.save()
    log(order, "reject_payment", by, user, message.strip())
    transaction.on_commit(lambda: notifications.rejected(order, message.strip()))
    return order


def paid_online(purchase, payment):
    """Called by payments once the gateway confirmed a payment for this purchase's House orders."""
    ids = (payment.meta or {}).get("orders") or []
    for order in Order.objects.select_for_update().filter(pk__in=ids, purchase=purchase):
        if order.status in Order.OPEN:
            order.status = Order.Status.PAID
            order.paid_at = timezone.now()
            order.paid_online = True
            order.payment_reference = payment.ref_id
            order.save()
            log(order, "paid_online", BUYER, message=f"شماره پیگیری {payment.ref_id}")
            transaction.on_commit(lambda o=order: notifications.paid(o))
        else:
            # Paid after it was cancelled (or paid twice): staff must refund or reopen it.
            order.staff_note = (order.staff_note + "\n" if order.staff_note else "") + (
                f"هشدار: پرداخت آنلاین {payment.ref_id} برای این سفارش در وضعیت «{order.get_status_display()}» رسید.")
            order.save(update_fields=["staff_note"])
            log(order, "note", SYSTEM, message="پرداخت آنلاین برای سفارشی که منتظر پرداخت نبود رسید؛ بررسی شود.")


# ---------------------------------------------------------------------------
# Shipping, cancelling, settlement
# ---------------------------------------------------------------------------


@transaction.atomic
def ship(order, user, tracking_code="", message="", by=SELLER):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.PAID:
        raise OrderError("فقط سفارش پرداخت‌شده را می‌توان ارسال کرد.")
    order.status = Order.Status.SHIPPED
    order.shipped_at = timezone.now()
    order.tracking_code = tracking_code.strip()[:100]
    order.shipping_message = message.strip()
    order.save()
    log(order, "ship", by, user, message.strip())
    transaction.on_commit(lambda: notifications.shipped(order))
    return order


@transaction.atomic
def complete(order, user, by=SELLER):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.SHIPPED:
        raise OrderError("فقط سفارش ارسال‌شده را می‌توان تحویل‌شده ثبت کرد.")
    order.status = Order.Status.COMPLETED
    order.completed_at = timezone.now()
    order.save()
    log(order, "complete", by, user)
    return order


def seller_can_cancel(order):
    if order.payment_mode == Seller.Mode.PRODUCER:
        return order.status in Order.CANCELLABLE
    return order.status in Order.OPEN  # after the House received the money, only staff cancel (refund)


@transaction.atomic
def cancel(order, user, reason, by=STAFF):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in Order.CANCELLABLE:
        raise OrderError("سفارش ارسال‌شده یا بسته را نمی‌توان لغو کرد.")
    if by == SELLER and not seller_can_cancel(order):
        raise OrderError("این سفارش پرداخت شده است؛ برای لغو و بازگرداندن پول با دبیرخانه تماس بگیرید.")
    if not reason.strip():
        raise OrderError("دلیل لغو را بنویسید؛ برای خریدار فرستاده می‌شود.")
    was_paid = order.status == Order.Status.PAID
    order.status = Order.Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancel_reason = reason.strip()
    order.save()
    _return_stock(order)
    log(order, "cancel", by, user, reason.strip())
    transaction.on_commit(lambda: notifications.cancelled(order, was_paid, by))
    return order


@transaction.atomic
def request_return(order, reason):
    """The buyer asks to return a shipped or delivered order (within ShopSettings.return_days)."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.can_request_return():
        raise OrderError("برای این سفارش دیگر نمی‌توان درخواست مرجوعی داد.")
    if not reason.strip():
        raise OrderError("دلیل مرجوعی را بنویسید.")
    order.return_requested_at = timezone.now()
    order.return_reason = reason.strip()
    order.save(update_fields=["return_requested_at", "return_reason"])
    log(order, "return_request", BUYER, None, reason.strip())
    transaction.on_commit(lambda: notifications.return_requested(order))
    return order


def can_record_refund(order, by):
    """Staff record refunds for every order; a producer only for orders paid directly to them."""
    return by == STAFF or not order.is_house


@transaction.atomic
def refund(order, user, amount, reference="", message="", restock=True, by=STAFF):
    """Record that the goods came back (or the order was undone after payment) and the money was paid back."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in Order.REFUNDABLE:
        raise OrderError("فقط سفارش پرداخت‌شده را می‌توان مرجوع و بازپرداخت کرد.")
    if not can_record_refund(order, by):
        raise OrderError("بازپرداخت سفارش‌هایی که به حساب خانه پرداخت شده‌اند را دبیرخانه ثبت می‌کند.")
    if amount is None or amount <= 0 or amount > order.total:
        raise OrderError("مبلغ بازپرداخت باید بیشتر از صفر و حداکثر برابر مبلغ سفارش باشد.")
    order.status = Order.Status.RETURNED
    order.refunded_at = timezone.now()
    order.refund_amount = amount
    order.refund_reference = reference.strip()[:100]
    order.save()
    if restock:
        _return_stock(order)
    log(order, "refund", by, user, message.strip())
    transaction.on_commit(lambda: notifications.refunded(order, message.strip()))
    return order


@transaction.atomic
def settle(order, user, reference=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.needs_settlement:
        raise OrderError("این سفارش تسویه‌ای ندارد یا پیش‌تر تسویه شده است.")
    order.settled_at = timezone.now()
    order.settlement_reference = reference.strip()[:100]
    order.save()
    log(order, "settle", STAFF, user, reference.strip())
    return order


def cancel_overdue(today=None):
    """Daily: cancel orders not paid within ShopSettings.payment_days and give their stock back."""
    shop = ShopSettings.load()
    if not shop.payment_days:
        return 0
    now = timezone.now() if today is None else timezone.make_aware(
        timezone.datetime.combine(today, timezone.datetime.min.time()))
    limit = now - timezone.timedelta(days=shop.payment_days)
    count = 0
    # A rejected receipt restarts the clock, so the buyer has the full time to send a correct one.
    recently_rejected = OrderEvent.objects.filter(order=OuterRef("pk"), action="reject_payment", created_at__gte=limit)
    for order in Order.objects.filter(status=Order.Status.AWAITING_PAYMENT, created_at__lt=limit).exclude(
            Exists(recently_rejected)):
        cancel(order, None, "مهلت پرداخت سفارش به پایان رسید.", by=SYSTEM)
        count += 1
    return count
