import uuid

from django import forms
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting

from core.models import BilingualMixin


@register_setting(icon="password")
class PaymentSettings(BaseGenericSetting):
    class Provider(models.TextChoices):
        ZARINPAL = "zarinpal", "زرین‌پال"
        IDPAY = "idpay", "آیدی‌پی (IDPay)"
        TEST = "test", "درگاه آزمایشی (فقط برای آزمون؛ پول واقعی جابه‌جا نمی‌شود)"

    enabled = models.BooleanField(
        "پرداخت آنلاین فعال است", default=False,
        help_text="پس از گرفتن نماد اعتماد الکترونیکی (اینماد) و ثبت درگاه روشن کنید. "
                  "تا خاموش است، پرداخت فقط با واریز به حساب و فرستادن رسید انجام می‌شود.",
    )
    provider = models.CharField("درگاه پرداخت", max_length=20, choices=Provider.choices, default=Provider.ZARINPAL)
    merchant_id = models.CharField(
        "کد پذیرنده (مرچنت) یا کلید API", max_length=255, blank=True,
        help_text="از پنل درگاه بگیرید. اگر متغیر محیطی PAYMENT_MERCHANT_ID روی سرور تنظیم شده باشد، آن به‌کار می‌رود.",
    )
    sandbox = models.BooleanField(
        "حالت آزمایشی (سندباکس) درگاه", default=False,
        help_text="برای آزمودن درگاه واقعی پیش از راه‌اندازی؛ در این حالت پولی جابه‌جا نمی‌شود",
    )

    for_orders = models.BooleanField("پرداخت آنلاین سفارش‌های فروشگاه", default=True,
                                     help_text="فقط سفارش‌هایی که پولشان به حساب خانه واریز می‌شود")
    for_application_fee = models.BooleanField("پرداخت آنلاین هزینه درخواست عضویت", default=True)
    for_dues = models.BooleanField("پرداخت آنلاین حق عضویت سالانه", default=True)

    button_label = models.CharField("متن دکمه پرداخت (فارسی)", max_length=60, default="پرداخت آنلاین")
    button_label_en = models.CharField("متن دکمه پرداخت (انگلیسی)", max_length=60, default="Pay online")
    note = models.CharField(
        "توضیح کنار دکمه (فارسی)", max_length=255, blank=True,
        default="با همه کارت‌های بانکی عضو شتاب. پس از پرداخت به همین صفحه برمی‌گردید.",
    )
    note_en = models.CharField(
        "توضیح کنار دکمه (انگلیسی)", max_length=255, blank=True,
        default="With any Iranian (Shetab) bank card. You come back to this page after paying.",
    )

    panels = [
        FieldPanel("enabled"),
        MultiFieldPanel(
            [FieldPanel("provider"),
             FieldPanel("merchant_id", widget=forms.PasswordInput(render_value=True)),
             FieldPanel("sandbox")],
            heading="درگاه",
        ),
        MultiFieldPanel([FieldPanel("for_orders"), FieldPanel("for_application_fee"), FieldPanel("for_dues")],
                        heading="کجا پرداخت آنلاین پیشنهاد شود"),
        MultiFieldPanel([FieldPanel("button_label"), FieldPanel("button_label_en"),
                         FieldPanel("note"), FieldPanel("note_en")], heading="متن‌ها"),
    ]

    class Meta:
        verbose_name = "تنظیمات پرداخت آنلاین"

    def tr(self, field):
        return BilingualMixin.tr(self, field)

    @property
    def effective_merchant_id(self):
        return getattr(settings, "PAYMENT_MERCHANT_ID", "") or self.merchant_id

    def enabled_for(self, purpose):
        flag = {"order": self.for_orders, "application_fee": self.for_application_fee, "dues": self.for_dues}
        return self.enabled and flag.get(purpose, False)


class Payment(models.Model):
    """One attempt to pay online. Only a verified attempt (status paid) settles anything."""

    class Status(models.TextChoices):
        STARTED = "started", "به درگاه رفت"
        PAID = "paid", "پرداخت شد"
        FAILED = "failed", "ناموفق یا لغو شد"

    PURPOSES = [
        ("order", "سفارش فروشگاه"),
        ("application_fee", "هزینه درخواست عضویت"),
        ("dues", "حق عضویت سالانه"),
    ]

    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    purpose = models.CharField("بابت", max_length=30, choices=PURPOSES)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    meta = models.JSONField(default=dict, blank=True)

    amount = models.PositiveBigIntegerField("مبلغ (ریال)")
    description = models.CharField("شرح", max_length=255, blank=True)
    mobile = models.CharField("همراه پرداخت‌کننده", max_length=40, blank=True)
    email = models.CharField("ایمیل پرداخت‌کننده", max_length=254, blank=True)
    language = models.CharField("زبان", max_length=5, default="fa")
    return_url = models.CharField("بازگشت به", max_length=500)

    provider = models.CharField("درگاه", max_length=20)
    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.STARTED, db_index=True)
    authority = models.CharField("شناسه تراکنش درگاه", max_length=100, blank=True, db_index=True)
    ref_id = models.CharField("شماره پیگیری بانکی", max_length=100, blank=True)
    card = models.CharField("کارت پرداخت‌کننده", max_length=40, blank=True)
    error = models.CharField("خطا", max_length=255, blank=True)
    raw = models.JSONField("پاسخ درگاه", default=dict, blank=True)

    created_at = models.DateTimeField("آغاز", auto_now_add=True)
    paid_at = models.DateTimeField("تاریخ پرداخت", null=True, blank=True)

    class Meta:
        verbose_name = "پرداخت آنلاین"
        verbose_name_plural = "پرداخت‌های آنلاین"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.get_purpose_display()} | {self.amount} | {self.get_status_display()}"

    @property
    def is_paid(self):
        return self.status == self.Status.PAID

    @classmethod
    def for_object(cls, obj):
        return cls.objects.filter(content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk)
