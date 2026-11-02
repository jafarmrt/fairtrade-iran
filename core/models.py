"""
Site-wide settings that the secretariat and PR working group edit from the
admin panel (Settings menu). Nothing here is hard-coded in templates.
"""

from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList, TabbedInterface
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting


def is_english():
    return (get_language() or "fa").startswith("en")


class BilingualMixin:
    """Helpers for models that store Persian in `field` and English in `field_en`."""

    def tr(self, field):
        if is_english():
            value = getattr(self, f"{field}_en", "")
            if value:
                return value
        return getattr(self, field, "")

    @property
    def has_english(self):
        return bool(getattr(self, "name_en", ""))


@register_setting(icon="site")
class SiteSettings(BaseGenericSetting):
    site_name = models.CharField(_("نام سایت (فارسی)"), max_length=120, default="خانه تجارت عادلانه ایران")
    site_name_en = models.CharField(_("نام سایت (انگلیسی)"), max_length=120, default="Fair Trade House of Iran")
    tagline = models.CharField(_("شعار (فارسی)"), max_length=200, blank=True)
    tagline_en = models.CharField(_("شعار (انگلیسی)"), max_length=200, blank=True)

    logo = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("لوگو"), null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text=_("نسخه تیره لوگو برای زمینه روشن"),
    )
    logo_light = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("لوگوی روشن"), null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text=_("نسخه سفید لوگو برای زمینه تیره (پانویس)"),
    )
    logo_en = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("لوگوی انگلیسی"), null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text=_("اگر خالی باشد، در نسخه انگلیسی هم لوگوی فارسی نمایش داده می‌شود"),
    )

    email = models.EmailField(_("ایمیل"), blank=True)
    phone = models.CharField(_("تلفن"), max_length=40, blank=True)
    address = models.TextField(_("نشانی (فارسی)"), blank=True)
    address_en = models.TextField(_("نشانی (انگلیسی)"), blank=True)

    instagram_url = models.URLField(_("اینستاگرام"), blank=True)
    telegram_url = models.URLField(_("تلگرام"), blank=True)
    linkedin_url = models.URLField(_("لینکدین"), blank=True)
    aparat_url = models.URLField(_("آپارات"), blank=True)

    footer_text = models.TextField(_("متن پانویس (فارسی)"), blank=True)
    footer_text_en = models.TextField(_("متن پانویس (انگلیسی)"), blank=True)

    notification_email = models.EmailField(
        _("ایمیل دبیرخانه برای اعلان‌ها"), blank=True,
        help_text=_("درخواست‌های عضویت و پیام‌های تماس به این نشانی خبر داده می‌شوند"),
    )

    panels = [
        MultiFieldPanel(
            [FieldPanel("site_name"), FieldPanel("site_name_en"), FieldPanel("tagline"), FieldPanel("tagline_en")],
            heading=_("نام و شعار"),
        ),
        MultiFieldPanel([FieldPanel("logo"), FieldPanel("logo_light"), FieldPanel("logo_en")], heading=_("لوگو")),
        MultiFieldPanel(
            [FieldPanel("email"), FieldPanel("phone"), FieldPanel("address"), FieldPanel("address_en"),
             FieldPanel("notification_email")],
            heading=_("اطلاعات تماس"),
        ),
        MultiFieldPanel(
            [FieldPanel("instagram_url"), FieldPanel("telegram_url"), FieldPanel("linkedin_url"), FieldPanel("aparat_url")],
            heading=_("شبکه‌های اجتماعی"),
        ),
        MultiFieldPanel([FieldPanel("footer_text"), FieldPanel("footer_text_en")], heading=_("پانویس")),
    ]

    class Meta:
        verbose_name = _("تنظیمات سایت")

    def tr(self, field):
        return BilingualMixin.tr(self, field)


@register_setting(icon="tasks")
class MembershipSettings(BaseGenericSetting):
    """Fees, bank details and deadlines, as approved by the General Assembly."""

    application_fee_producer = models.PositiveBigIntegerField(_("هزینه درخواست: تولیدکننده (ریال)"), null=True, blank=True)
    application_fee_institution = models.PositiveBigIntegerField(_("هزینه درخواست: نهاد حمایتی (ریال)"), null=True, blank=True)
    application_fee_network = models.PositiveBigIntegerField(_("هزینه درخواست: شبکه تجارت عادلانه (ریال)"), null=True, blank=True)
    application_fee_individual = models.PositiveBigIntegerField(_("هزینه درخواست: فرد حامی (ریال)"), null=True, blank=True)

    annual_fee_producer = models.PositiveBigIntegerField(_("حق عضویت سالانه: تولیدکننده (ریال)"), null=True, blank=True)
    annual_fee_institution = models.PositiveBigIntegerField(_("حق عضویت سالانه: نهاد حمایتی (ریال)"), null=True, blank=True)
    annual_fee_network = models.PositiveBigIntegerField(_("حق عضویت سالانه: شبکه تجارت عادلانه (ریال)"), null=True, blank=True)
    annual_fee_individual = models.PositiveBigIntegerField(_("حق عضویت سالانه: فرد حامی (ریال)"), null=True, blank=True)

    account_holder = models.CharField(_("نام صاحب حساب"), max_length=120, blank=True)
    bank_name = models.CharField(_("نام بانک"), max_length=80, blank=True)
    card_number = models.CharField(_("شماره کارت"), max_length=30, blank=True)
    sheba = models.CharField(_("شماره شبا"), max_length=40, blank=True)

    secretariat_review_days = models.PositiveSmallIntegerField(_("مهلت کنترل مدارک دبیرخانه (روز)"), default=7)
    commission_review_days = models.PositiveSmallIntegerField(_("مهلت ارزیابی کمیسیون (روز)"), default=30)
    trial_period_months = models.PositiveSmallIntegerField(_("دوره آزمایشی (ماه)"), default=3)

    applications_open = models.BooleanField(_("پذیرش درخواست عضویت فعال است"), default=True)

    fee_panels = [
        MultiFieldPanel(
            [FieldPanel("application_fee_producer"), FieldPanel("application_fee_institution"),
             FieldPanel("application_fee_network"), FieldPanel("application_fee_individual")],
            heading=_("هزینه درخواست عضویت (غیرقابل استرداد)"),
        ),
        MultiFieldPanel(
            [FieldPanel("annual_fee_producer"), FieldPanel("annual_fee_institution"),
             FieldPanel("annual_fee_network"), FieldPanel("annual_fee_individual")],
            heading=_("حق عضویت سالانه"),
        ),
    ]
    bank_panels = [
        FieldPanel("account_holder"), FieldPanel("bank_name"), FieldPanel("card_number"), FieldPanel("sheba"),
    ]
    process_panels = [
        FieldPanel("applications_open"),
        FieldPanel("secretariat_review_days"),
        FieldPanel("commission_review_days"),
        FieldPanel("trial_period_months"),
    ]
    edit_handler = TabbedInterface([
        ObjectList(fee_panels, heading=_("مبالغ")),
        ObjectList(bank_panels, heading=_("حساب بانکی")),
        ObjectList(process_panels, heading=_("فرایند و مهلت‌ها")),
    ])

    class Meta:
        verbose_name = _("تنظیمات عضویت")

    def application_fee_for(self, member_type):
        return getattr(self, f"application_fee_{member_type}", None)

    def annual_fee_for(self, member_type):
        return getattr(self, f"annual_fee_{member_type}", None)

    @property
    def has_bank_details(self):
        return bool(self.card_number or self.sheba)
