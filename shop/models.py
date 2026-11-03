import os
import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel

from core.models import BilingualMixin, is_english
from members.models import Member

from .storage import receipt_storage


def _label(choices_en, value, display):
    return choices_en.get(value, display) if is_english() else display


class Seller(BilingualMixin, ClusterableModel):
    """How one member sells through the site's cart. Staff choose the mode; the member edits the rest in the panel."""

    class Mode(models.TextChoices):
        NONE = "none", "فقط لینک خرید مستقیم (بدون سبد خرید)"
        HOUSE = "house", "پرداخت به حساب خانه"
        PRODUCER = "producer", "پرداخت مستقیم به تولیدکننده"

    member = models.OneToOneField(Member, verbose_name="عضو", on_delete=models.CASCADE, related_name="seller")
    mode = models.CharField("شیوه فروش از سایت", max_length=20, choices=Mode.choices, default=Mode.NONE,
                            help_text="فقط کارکنان خانه این را تغییر می‌دهند")
    commission_percent = models.DecimalField(
        "کارمزد خانه برای این فروشنده (درصد)", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="اگر خالی باشد، کارمزد «تنظیمات فروشگاه» به‌کار می‌رود",
    )

    account_holder = models.CharField("نام صاحب حساب", max_length=120, blank=True)
    bank_name = models.CharField("نام بانک", max_length=80, blank=True)
    card_number = models.CharField("شماره کارت", max_length=30, blank=True)
    sheba = models.CharField("شماره شبا", max_length=40, blank=True,
                             help_text="برای پرداخت مستقیم خریدار و نیز واریز سهم تولیدکننده از فروش با پرداخت به خانه")

    shipping_fee = models.PositiveBigIntegerField("هزینه ارسال هر سفارش (ریال)", default=0)
    free_shipping_over = models.PositiveBigIntegerField(
        "ارسال رایگان برای خرید بیش از (ریال)", null=True, blank=True)
    prep_days = models.PositiveSmallIntegerField("آماده‌سازی و ارسال (روز کاری)", default=3)
    shipping_note = models.CharField("توضیح ارسال (فارسی)", max_length=255, blank=True,
                                     help_text="مثلاً «ارسال با پست پیشتاز به سراسر ایران»")
    shipping_note_en = models.CharField("توضیح ارسال (انگلیسی)", max_length=255, blank=True)
    order_mobile = models.CharField("همراه برای اعلان سفارش", max_length=40, blank=True,
                                    help_text="اگر خالی باشد، تلفن پرونده عضویت یا تلفن عمومی")
    order_email = models.EmailField("ایمیل برای اعلان سفارش", blank=True,
                                    help_text="جز مدیران پنل این عضو، سفارش‌ها به این نشانی هم خبر داده می‌شود")

    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel("member"),
        FieldRowPanel([FieldPanel("mode"), FieldPanel("commission_percent")]),
        MultiFieldPanel([FieldPanel("account_holder"), FieldPanel("bank_name"), FieldPanel("card_number"),
                         FieldPanel("sheba")], heading="حساب بانکی فروشنده"),
        MultiFieldPanel([FieldPanel("shipping_fee"), FieldPanel("free_shipping_over"), FieldPanel("prep_days"),
                         FieldPanel("shipping_note"), FieldPanel("shipping_note_en")], heading="ارسال"),
        InlinePanel("shipping_options", heading="روش‌های ارسال",
                    help_text="اگر روشی تعریف شود، خریدار یکی را انتخاب می‌کند و «هزینه ارسال هر سفارش» به‌کار نمی‌رود"),
        MultiFieldPanel([FieldPanel("order_mobile"), FieldPanel("order_email")], heading="اعلان سفارش"),
    ]

    class Meta:
        verbose_name = "فروشنده"
        verbose_name_plural = "فروشندگان"
        ordering = ["member__name"]

    def __str__(self):
        return f"{self.member} ({self.get_mode_display()})"

    def clean(self):
        super().clean()
        from core.iran import clean_bank_fields

        clean_bank_fields(self)

    @classmethod
    def mode_for(cls, member):
        seller = getattr(member, "_seller_cache", None)
        if seller is None:
            seller = cls.objects.filter(member=member).first() or cls(member=member)
            member._seller_cache = seller
        return seller.mode

    @classmethod
    def for_member(cls, member):
        return cls.objects.filter(member=member).first() or cls(member=member)

    @property
    def has_bank_details(self):
        return bool(self.card_number or self.sheba)

    def effective_commission(self, shop):
        return self.commission_percent if self.commission_percent is not None else shop.commission_percent

    def shipping_for(self, subtotal, option=None):
        if self.free_shipping_over and subtotal >= self.free_shipping_over:
            return 0
        return option.fee if option is not None else self.shipping_fee

    def active_shipping_options(self):
        if not self.pk:
            return []
        cached = getattr(self, "_options_cache", None)
        if cached is None:
            cached = self._options_cache = list(self.shipping_options.filter(active=True))
        return cached


class ShippingOption(BilingualMixin, models.Model):
    """One way a seller ships (پست پیشتاز، تیپاکس، پیک…), with its own cost."""

    seller = ParentalKey(Seller, on_delete=models.CASCADE, related_name="shipping_options")
    name = models.CharField("نام روش (فارسی)", max_length=80, help_text="مثلاً «پست پیشتاز»، «تیپاکس» یا «پیک در تهران»")
    name_en = models.CharField("نام روش (انگلیسی)", max_length=80, blank=True)
    fee = models.PositiveBigIntegerField("هزینه (ریال)", default=0)
    delivery_time = models.CharField("زمان رسیدن (فارسی)", max_length=80, blank=True,
                                     help_text="مثلاً «۲ تا ۴ روز کاری»")
    delivery_time_en = models.CharField("زمان رسیدن (انگلیسی)", max_length=80, blank=True)
    active = models.BooleanField("فعال", default=True)
    sort_order = models.PositiveSmallIntegerField("ترتیب", default=0)

    panels = [
        FieldRowPanel([FieldPanel("name"), FieldPanel("name_en")]),
        FieldRowPanel([FieldPanel("fee"), FieldPanel("active")]),
        FieldRowPanel([FieldPanel("delivery_time"), FieldPanel("delivery_time_en")]),
    ]

    class Meta:
        verbose_name = "روش ارسال"
        verbose_name_plural = "روش‌های ارسال"
        ordering = ["sort_order", "fee", "pk"]

    def __str__(self):
        return self.name


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_purchase_code():
    while True:
        code = "S-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(7))
        if not Purchase.objects.filter(code=code).exists():
            return code


class Purchase(models.Model):
    """One checkout by a buyer. Its orders (one per producer) are paid and shipped separately."""

    code = models.CharField("کد سفارش", max_length=20, unique=True, editable=False)
    buyer_name = models.CharField("نام خریدار", max_length=150)
    phone = models.CharField("تلفن همراه", max_length=40)
    email = models.EmailField("ایمیل", blank=True)
    province = models.CharField("استان", max_length=60, blank=True)
    city = models.CharField("شهر", max_length=80)
    address = models.TextField("نشانی")
    postal_code = models.CharField("کد پستی", max_length=20, blank=True)
    note = models.TextField("توضیح خریدار", blank=True)
    language = models.CharField("زبان", max_length=5, default="fa")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+")
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "خرید"
        verbose_name_plural = "خریدها"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} | {self.buyer_name}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = new_purchase_code()
        super().save(*args, **kwargs)

    @property
    def total(self):
        return sum(o.total for o in self.orders.all())

    def orders_payable_online(self):
        return [o for o in self.orders.all()
                if o.payment_mode == Seller.Mode.HOUSE and o.status == Order.Status.AWAITING_PAYMENT]

    @property
    def full_address(self):
        parts = [self.province, self.city, self.address]
        text = "، ".join(p for p in parts if p)
        if self.postal_code:
            text += f" (کد پستی {self.postal_code})"
        return text


class Order(models.Model):
    """The part of a purchase that one producer prepares and ships."""

    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment", "در انتظار پرداخت"
        PAYMENT_REVIEW = "payment_review", "رسید در انتظار بررسی"
        PAID = "paid", "پرداخت شد؛ در حال آماده‌سازی"
        SHIPPED = "shipped", "ارسال شد"
        COMPLETED = "completed", "تحویل شد"
        CANCELLED = "cancelled", "لغو شد"
        RETURNED = "returned", "مرجوع شد؛ مبلغ بازپرداخت شد"

    STATUS_EN = {
        Status.AWAITING_PAYMENT: "Awaiting payment",
        Status.PAYMENT_REVIEW: "Payment being checked",
        Status.PAID: "Paid, being prepared",
        Status.SHIPPED: "Shipped",
        Status.COMPLETED: "Delivered",
        Status.CANCELLED: "Cancelled",
        Status.RETURNED: "Returned and refunded",
    }
    OPEN = (Status.AWAITING_PAYMENT, Status.PAYMENT_REVIEW)
    REFUNDABLE = (Status.PAID, Status.SHIPPED, Status.COMPLETED)
    CANCELLABLE = (Status.AWAITING_PAYMENT, Status.PAYMENT_REVIEW, Status.PAID)

    purchase = models.ForeignKey(Purchase, verbose_name="خرید", on_delete=models.CASCADE, related_name="orders")
    member = models.ForeignKey(Member, verbose_name="تولیدکننده", on_delete=models.PROTECT, related_name="orders")
    payment_mode = models.CharField("پرداخت به", max_length=20, choices=Seller.Mode.choices)
    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.AWAITING_PAYMENT,
                              db_index=True)

    subtotal = models.PositiveBigIntegerField("جمع کالاها (ریال)")
    shipping = models.PositiveBigIntegerField("هزینه ارسال (ریال)", default=0)
    total = models.PositiveBigIntegerField("مبلغ کل (ریال)")
    commission_percent = models.DecimalField("درصد کارمزد خانه", max_digits=5, decimal_places=2, default=0)
    commission = models.PositiveBigIntegerField("کارمزد خانه (ریال)", default=0)

    # payment
    payment_reference = models.CharField("شماره پیگیری پرداخت", max_length=100, blank=True)
    payer_note = models.TextField("توضیح پرداخت خریدار", blank=True)
    receipt = models.FileField("تصویر رسید", storage=receipt_storage, upload_to="receipts/%Y/%m/",
                               max_length=255, blank=True)
    receipt_name = models.CharField("نام اصلی فایل رسید", max_length=255, blank=True)
    paid_at = models.DateTimeField("تاریخ تأیید پرداخت", null=True, blank=True)
    paid_online = models.BooleanField("پرداخت آنلاین", default=False)

    # shipping
    shipping_method = models.CharField("روش ارسال", max_length=80, blank=True)
    shipping_method_en = models.CharField("روش ارسال (انگلیسی)", max_length=80, blank=True)
    shipped_at = models.DateTimeField("تاریخ ارسال", null=True, blank=True)
    tracking_code = models.CharField("کد رهگیری مرسوله", max_length=100, blank=True)
    shipping_message = models.TextField("پیام ارسال به خریدار", blank=True)
    completed_at = models.DateTimeField("تاریخ تحویل", null=True, blank=True)

    return_requested_at = models.DateTimeField("درخواست مرجوعی", null=True, blank=True)
    return_reason = models.TextField("دلیل مرجوعی", blank=True)
    refunded_at = models.DateTimeField("تاریخ بازپرداخت", null=True, blank=True)
    refund_amount = models.PositiveBigIntegerField("مبلغ بازپرداخت (ریال)", null=True, blank=True)
    refund_reference = models.CharField("شماره پیگیری بازپرداخت", max_length=100, blank=True)
    cancelled_at = models.DateTimeField("تاریخ لغو", null=True, blank=True)
    cancel_reason = models.TextField("دلیل لغو", blank=True)

    # settlement between the House and the producer
    settled_at = models.DateTimeField("تسویه با تولیدکننده", null=True, blank=True)
    settlement_reference = models.CharField("شماره پیگیری تسویه", max_length=100, blank=True)

    staff_note = models.TextField("یادداشت داخلی", blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", default=timezone.now)

    class Meta:
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"
        ordering = ["-created_at"]
        permissions = [("manage_orders", "رسیدگی به سفارش‌ها، تأیید پرداخت و تسویه با تولیدکنندگان")]

    def __str__(self):
        return f"{self.code} | {self.member}"

    @property
    def code(self):
        return f"{self.purchase.code}-{self.pk}"

    @property
    def status_display(self):
        return _label(self.STATUS_EN, self.status, self.get_status_display())

    @property
    def is_house(self):
        return self.payment_mode == Seller.Mode.HOUSE

    def can_request_return(self, shop=None):
        """The buyer may ask to return a delivered or shipped order within ShopSettings.return_days."""
        from products.models import ShopSettings

        shop = shop or ShopSettings.load()
        since = self.completed_at or self.shipped_at
        if not shop.return_days or self.return_requested_at or since is None:
            return False
        if self.status not in (self.Status.SHIPPED, self.Status.COMPLETED):
            return False
        return timezone.now() <= since + timezone.timedelta(days=shop.return_days)

    @property
    def shipping_method_display(self):
        return self.shipping_method_en if (is_english() and self.shipping_method_en) else self.shipping_method

    @property
    def producer_share(self):
        return self.total - self.commission

    @property
    def is_open(self):
        return self.status in self.OPEN

    @property
    def needs_settlement(self):
        """House-paid orders whose producer has not been paid yet, or direct orders whose commission is due."""
        return (self.status in (self.Status.PAID, self.Status.SHIPPED, self.Status.COMPLETED)
                and self.settled_at is None and (self.is_house or self.commission > 0))

    @staticmethod
    def commission_for(subtotal, percent):
        return int((Decimal(subtotal) * Decimal(percent) / 100).quantize(Decimal("1")))

    @property
    def receipt_filename(self):
        return self.receipt_name or os.path.basename(self.receipt.name)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", verbose_name="محصول", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="order_items")
    name = models.CharField("نام محصول", max_length=160)
    name_en = models.CharField("نام انگلیسی", max_length=160, blank=True)
    unit_price = models.PositiveBigIntegerField("قیمت واحد (ریال)")
    quantity = models.PositiveIntegerField("تعداد")

    class Meta:
        verbose_name = "قلم سفارش"
        verbose_name_plural = "اقلام سفارش"

    def __str__(self):
        return f"{self.name} × {self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def tr_name(self):
        return self.name_en if (is_english() and self.name_en) else self.name


class OrderEvent(models.Model):
    """History of an order, shown to staff and (when it has a message) to the seller and buyer."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    created_at = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+")
    by = models.CharField("انجام‌دهنده", max_length=20, blank=True)  # buyer, seller, staff, system
    action = models.CharField("اقدام", max_length=40)
    status = models.CharField("وضعیت پس از اقدام", max_length=20, blank=True)
    message = models.TextField("پیام", blank=True)

    class Meta:
        ordering = ["created_at"]

    ACTIONS = {
        "placed": ("سفارش ثبت شد", "Order placed"),
        "receipt": ("خریدار اطلاعات پرداخت را فرستاد", "Buyer sent payment details"),
        "paid_online": ("پرداخت آنلاین انجام شد", "Paid online"),
        "confirm_payment": ("پرداخت تأیید شد", "Payment confirmed"),
        "reject_payment": ("رسید پذیرفته نشد", "Receipt not accepted"),
        "ship": ("ارسال شد", "Shipped"),
        "complete": ("تحویل شد", "Delivered"),
        "cancel": ("لغو شد", "Cancelled"),
        "settle": ("تسویه با تولیدکننده ثبت شد", "Settled with the producer"),
        "return_request": ("خریدار درخواست مرجوعی داد", "Buyer asked to return the order"),
        "refund": ("مرجوعی و بازپرداخت ثبت شد", "Return and refund recorded"),
        "note": ("یادداشت", "Note"),
    }

    @property
    def action_display(self):
        fa, en = self.ACTIONS.get(self.action, (self.action, self.action))
        return en if is_english() else fa
