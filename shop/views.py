"""Public pages of the cart and orders. They are routes of the shop page (ProductIndexPage)."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect

from core import throttle
from core.iran import only_digits
from core.models import is_english
from payments.models import Payment, PaymentSettings
from payments.services import online_enabled, start_payment
from products.models import Product, ShopSettings

from . import services
from .cart import MAX_QUANTITY, Cart
from .forms import CheckoutForm, LookupForm, PaymentInfoForm
from .models import Order, Purchase

SESSION_PURCHASES = "shop_purchases"


def t(fa, en):
    return en if is_english() else fa


def sub(page, name, **kwargs):
    return page.url + page.reverse_subpage(name, kwargs=kwargs or None)


def render(page, request, template, context, suffix):
    return page.render(request, template=template, context_overrides={"routable_suffix": suffix, **context})


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def cart_view(page, request):
    shop = ShopSettings.load(request_or_site=request)
    cart = Cart(request)
    if request.method == "POST":
        action = request.POST.get("action", "add")
        product_id = _int(request.POST.get("product"))
        if action == "add":
            product = Product.visible().filter(pk=product_id).first()
            if product is None or not product.can_add_to_cart(shop):
                messages.error(request, t("این محصول از راه سبد خرید فروخته نمی‌شود.",
                                          "This product cannot be bought through the cart."))
                return redirect(sub(page, "cart"))
            quantity = max(1, min(_int(request.POST.get("quantity"), 1), MAX_QUANTITY))
            cart.add(product.pk, quantity)
            name = product.tr("name")
            messages.success(request, t(f"«{name}» به سبد خرید افزوده شد.", f"“{name}” was added to your cart."))
            if request.POST.get("next") == "product":
                return redirect(product.get_url())
        elif action == "update":
            for key in list(cart.data):
                if f"qty_{key}" in request.POST:
                    cart.set(key, _int(request.POST.get(f"qty_{key}"), 0))
        elif action == "remove":
            cart.set(product_id, 0)
        return redirect(sub(page, "cart"))
    groups = cart.groups()
    return render(page, request, "shop/cart.html", {
        "groups": groups,
        "cart_total": sum(g.total for g in groups),
        "shop": shop,
    }, "cart/")


def checkout(page, request):
    shop = ShopSettings.load(request_or_site=request)
    cart = Cart(request)
    groups = cart.groups()
    if not groups:
        return redirect(sub(page, "cart"))
    has_terms = bool(shop.tr("terms_text"))
    form = CheckoutForm(request.POST or None, has_terms=has_terms)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data.get("nickname"):
            return redirect(sub(page, "cart"))  # a bot filled the honeypot
        if throttle.hit(request, "checkout"):
            return throttle.throttled_response(request)
        try:
            purchase = services.place_order(cart, form.buyer(), language="en" if is_english() else "fa",
                                            user=request.user)
        except services.OrderError as e:
            messages.error(request, str(e))
            return redirect(sub(page, "cart"))
        remember(request, purchase)
        return redirect(sub(page, "order", code=purchase.code) + "?new=1")
    return render(page, request, "shop/checkout.html", {
        "groups": groups,
        "cart_total": sum(g.total for g in groups),
        "form": form,
        "shop": shop,
        "has_terms": has_terms,
    }, "checkout/")


def remember(request, purchase):
    codes = [c for c in request.session.get(SESSION_PURCHASES, []) if c != purchase.code]
    request.session[SESSION_PURCHASES] = ([purchase.code] + codes)[:20]


def can_see(request, purchase):
    return purchase.code in request.session.get(SESSION_PURCHASES, [])


def order_view(page, request, code):
    purchase = Purchase.objects.filter(code=code.upper()).first()
    if purchase is None or not can_see(request, purchase):
        lookup = sub(page, "orders")
        return redirect(f"{lookup}?code={code}")
    url = sub(page, "order", code=purchase.code)
    payment_forms = {}
    if request.method == "POST":
        step = request.POST.get("step")
        if step == "pay_online":
            return start_payment(request, "order", purchase, url)
        if step == "payment_info":
            form = PaymentInfoForm(request.POST, request.FILES)
            order = purchase.orders.filter(pk=_int(request.POST.get("order"))).first()
            if order is None:
                raise Http404
            if form.is_valid():
                try:
                    services.submit_payment(order, form.cleaned_data["reference"], form.cleaned_data["note"],
                                            form.cleaned_data.get("receipt"))
                except services.OrderError as e:
                    messages.error(request, str(e))
                else:
                    messages.success(request, t("اطلاعات پرداخت فرستاده شد. پس از بررسی خبرتان می‌کنیم.",
                                                "Payment details sent. We will let you know once they are checked."))
                    return redirect(url)
            payment_forms[order.pk] = form
    orders = list(purchase.orders.select_related("member").prefetch_related("items", "events"))
    shop = ShopSettings.load(request_or_site=request)
    from .models import Seller

    for order in orders:
        order.seller = Seller.for_member(order.member)
        order.account = shop.house_account() if order.is_house else order.seller
        order.payment_form = payment_forms.get(order.pk) or (
            PaymentInfoForm(initial={"order": order.pk}) if order.status == Order.Status.AWAITING_PAYMENT else None)
    payable = purchase.orders_payable_online()
    payment_state = request.GET.get("payment")
    return render(page, request, "shop/order.html", {
        "purchase": purchase,
        "orders": orders,
        "is_new": request.GET.get("new") == "1",
        "online": online_enabled("order") and bool(payable),
        "online_amount": sum(o.total for o in payable),
        "pay": PaymentSettings.load(),
        "payment_state": payment_state,
        "last_payment": Payment.for_object(purchase).first() if payment_state else None,
        "shop": shop,
    }, f"order/{purchase.code}/")


def lookup(page, request):
    form = LookupForm(request.POST or None, initial={"code": request.GET.get("code", "")})
    error = ""
    if request.method == "POST" and throttle.hit(request, "lookup"):
        return throttle.throttled_response(request)
    if request.method == "POST" and form.is_valid():
        digits = lambda s: only_digits(s)[-10:]  # noqa: E731  (Persian, Arabic or Latin digits; 0912… or +98912…)
        purchase = Purchase.objects.filter(code=form.cleaned_data["code"]).first()
        if purchase and digits(form.cleaned_data["phone"]) and digits(purchase.phone) == digits(form.cleaned_data["phone"]):
            remember(request, purchase)
            return redirect(sub(page, "order", code=purchase.code))
        error = t("سفارشی با این کد و شماره تلفن پیدا نشد.", "No order matches this code and phone number.")
    recent = list(Purchase.objects.filter(code__in=request.session.get(SESSION_PURCHASES, [])))
    return render(page, request, "shop/lookup.html", {"form": form, "error": error, "recent": recent}, "orders/")
