from django import forms
from django.conf import settings
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting

from core.admin_panels import technical_note

from .phone import mobile_list
from .registry import AUDIENCES, event_choices, get


@register_setting(icon="mail")
class SmsSettings(BaseGenericSetting):
    class Provider(models.TextChoices):
        CONSOLE = "console", "آزمایشی (فقط در گزارش سرور نوشته می‌شود)"
        KAVENEGAR = "kavenegar", "کاوه‌نگار"
        SMSIR = "smsir", "اس‌ام‌اس دات آی‌آر (sms.ir)"

    enabled = models.BooleanField(
        "ارسال پیامک فعال است", default=False,
        help_text="تا این گزینه روشن نشود، هیچ پیامکی فرستاده نمی‌شود. ایمیل‌ها مثل قبل فرستاده می‌شوند.",
    )
    provider = models.CharField("سامانه پیامک", max_length=20, choices=Provider.choices, default=Provider.CONSOLE)
    api_key = models.CharField(
        "کلید API", max_length=255, blank=True,
        help_text="از پنل سامانه پیامک بگیرید. اگر متغیر محیطی SMS_API_KEY روی سرور تنظیم شده باشد، آن به‌کار می‌رود.",
    )
    sender = models.CharField(
        "شماره خط فرستنده", max_length=30, blank=True,
        help_text="شماره خط اختصاصی یا خدماتی که در سامانه پیامک دارید",
    )
    secretariat_mobiles = models.TextField(
        "شماره همراه دبیرخانه", blank=True,
        help_text="برای اعلان‌های دبیرخانه (درخواست تازه، پیام تماس، یادآوری مهلت). چند شماره را با ویرگول یا خط تازه جدا کنید.",
    )
    commission_mobiles = models.TextField(
        "شماره همراه کمیسیون نظارتی", blank=True,
        help_text="برای پرونده‌های ارجاع‌شده به کمیسیون و شکایت‌های تازه. چند شماره را با ویرگول یا خط تازه جدا کنید.",
    )

    panels = [
        technical_note("سامانهٔ پیامک برای کد ورود اعضا و خبر دادن به دبیرخانه و کمیسیون. کلید و شمارهٔ فرستنده را شرکت پیامکی می‌دهد."),
        FieldPanel("enabled"),
        MultiFieldPanel(
            [FieldPanel("provider"),
             FieldPanel("api_key", widget=forms.PasswordInput(render_value=True)),
             FieldPanel("sender")],
            heading="سامانه پیامک",
        ),
        MultiFieldPanel([FieldPanel("secretariat_mobiles"), FieldPanel("commission_mobiles")], heading="گیرندگان داخلی"),
    ]

    class Meta:
        verbose_name = "تنظیمات پیامک"

    @property
    def effective_api_key(self):
        return getattr(settings, "SMS_API_KEY", "") or self.api_key

    def mobiles_for(self, role):
        return mobile_list(getattr(self, f"{role}_mobiles", ""))


class SmsTemplate(models.Model):
    event = models.CharField("رویداد", max_length=60, choices=event_choices, unique=True)
    active = models.BooleanField("ارسال شود", default=True)
    text = models.TextField(
        "متن (فارسی)",
        help_text="کوتاه بنویسید: هر پیامک فارسی حدود ۷۰ نویسه است و پیام بلندتر چند پیامک حساب می‌شود. "
                  "عبارت‌های داخل {} با اطلاعات پرونده پر می‌شوند، مثل {name} {code} {status} {deadline} {track_url} {admin_url} {site_name}.",
    )
    text_en = models.TextField("متن (انگلیسی)", blank=True, help_text="برای کسانی که فرم را به انگلیسی پر کرده‌اند")

    panels = [FieldPanel("event"), FieldPanel("active"), FieldPanel("text"), FieldPanel("text_en")]

    class Meta:
        verbose_name = "متن پیامک"
        verbose_name_plural = "متن‌های پیامک"
        ordering = ["event"]

    def __str__(self):
        return self.get_event_display()

    @property
    def audience(self):
        event = get(self.event)
        return AUDIENCES.get(event.audience, "") if event else ""
    audience.fget.short_description = "گیرنده"


class SmsLog(models.Model):
    created = models.DateTimeField("زمان", auto_now_add=True, db_index=True)
    event = models.CharField("رویداد", max_length=60, blank=True)
    recipient = models.CharField("گیرنده", max_length=20)
    text = models.TextField("متن")
    provider = models.CharField("سامانه", max_length=20, blank=True)
    success = models.BooleanField("موفق", default=False)
    error = models.TextField("خطا", blank=True)

    class Meta:
        verbose_name = "گزارش پیامک"
        verbose_name_plural = "گزارش پیامک‌ها"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.recipient} {self.created:%Y-%m-%d %H:%M}"
