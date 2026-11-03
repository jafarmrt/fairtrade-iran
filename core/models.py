"""
Site-wide settings that the secretariat and PR working group edit from the
admin panel (Settings menu). Nothing here is hard-coded in templates.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList, TabbedInterface
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField


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

    price_display = models.CharField(
        _("نمایش مبلغ‌ها"), max_length=10, default="toman",
        choices=[("toman", _("تومان")), ("rial", _("ریال")), ("both", _("تومان، با ریال در پرانتز"))],
        help_text=_("مبلغ‌ها همیشه به ریال ذخیره و به درگاه فرستاده می‌شوند؛ این گزینه فقط شیوه نمایش را تعیین می‌کند. "
                    "خانه‌های ورود مبلغ در پنل همچنان ریالی‌اند."),
    )

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
        FieldPanel("price_display"),
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
    reminder_days_before = models.PositiveSmallIntegerField(
        _("یادآوری مهلت (روز پیش از پایان)"), default=2,
        help_text=_("دبیرخانه و کمیسیون این تعداد روز پیش از پایان مهلت هر پرونده ایمیل یادآوری می‌گیرند"),
    )
    max_upload_mb = models.PositiveSmallIntegerField(_("حداکثر حجم هر فایل پیوست (مگابایت)"), default=10)
    allowed_upload_extensions = models.CharField(
        _("پسوندهای مجاز پیوست"), max_length=200, default="pdf, jpg, jpeg, png, docx, odt",
        help_text=_("با ویرگول جدا کنید"),
    )

    certificate_prefix = models.CharField(
        _("پیشوند شماره گواهی"), max_length=20, default="FTH",
        help_text=_("شماره گواهی به شکل پیشوند-سال-شماره ساخته می‌شود، مثلاً FTH-1405-0001"),
    )
    certificate_title = models.CharField(_("عنوان گواهی (فارسی)"), max_length=200, default="گواهی عضویت")
    certificate_title_en = models.CharField(_("عنوان گواهی (انگلیسی)"), max_length=200, default="Certificate of Membership")
    certificate_text = models.TextField(
        _("متن گواهی (فارسی)"), blank=True,
        help_text=_("می‌توانید از {name}، {type} و {date} در متن استفاده کنید"),
    )
    certificate_text_en = models.TextField(_("متن گواهی (انگلیسی)"), blank=True)
    certificate_signatory = models.CharField(_("نام امضاکننده گواهی (فارسی)"), max_length=120, blank=True)
    certificate_signatory_en = models.CharField(_("نام امضاکننده گواهی (انگلیسی)"), max_length=120, blank=True)
    certificate_signatory_title = models.CharField(_("سمت امضاکننده (فارسی)"), max_length=120, blank=True, default="دبیر اجرایی")
    certificate_signatory_title_en = models.CharField(_("سمت امضاکننده (انگلیسی)"), max_length=120, blank=True, default="Executive Secretary")
    certificate_validity_months = models.PositiveSmallIntegerField(
        _("اعتبار گواهی (ماه)"), null=True, blank=True, default=12,
        help_text=_("خالی بگذارید اگر گواهی تاریخ انقضا ندارد"),
    )

    # ---- annual dues, suspension and cancellation (sections 1.7 and 1.8 of the governance document) ----
    DUES_FIXED = "fixed"
    DUES_ANNIVERSARY = "anniversary"
    DUES_CYCLE_CHOICES = [
        (DUES_FIXED, "تاریخ ثابت برای همه اعضا (مثلاً اول فروردین)"),
        (DUES_ANNIVERSARY, "سالگرد عضویت هر عضو"),
    ]
    dues_enabled = models.BooleanField(
        _("صدور خودکار حق عضویت سالانه فعال است"), default=True,
        help_text=_("اگر خاموش باشد، حق عضویت فقط دستی از صفحه وضعیت هر عضو ثبت می‌شود"),
    )
    dues_cycle = models.CharField(_("آغاز سال عضویت"), max_length=20, choices=DUES_CYCLE_CHOICES, default=DUES_FIXED)
    dues_start_month = models.PositiveSmallIntegerField(
        _("ماه آغاز سال عضویت (شمسی)"), default=1, validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text=_("برای «تاریخ ثابت»: ۱ یعنی فروردین، ۷ یعنی مهر"),
    )
    dues_start_day = models.PositiveSmallIntegerField(
        _("روز آغاز سال عضویت (شمسی)"), default=1, validators=[MinValueValidator(1), MaxValueValidator(29)],
    )
    dues_for_trial = models.BooleanField(
        _("اعضای آزمایشی هم حق عضویت سالانه بپردازند"), default=False,
    )
    dues_issue_days_before = models.PositiveSmallIntegerField(
        _("صدور صورت‌حساب (روز پیش از آغاز سال عضویت)"), default=30,
        help_text=_("در این روز برای عضو ایمیل صورت‌حساب فرستاده می‌شود و در پنل اعضا دیده می‌شود"),
    )
    dues_payment_days = models.PositiveSmallIntegerField(
        _("مهلت پرداخت (روز پس از آغاز سال عضویت)"), default=30,
    )
    dues_reminder_days_before = models.PositiveSmallIntegerField(
        _("یادآوری پرداخت (روز پیش از پایان مهلت)"), default=7,
    )
    dues_auto_warning = models.BooleanField(
        _("پس از پایان مهلت، اخطار کتبی خودکار فرستاده شود"), default=True,
        help_text=_("اگر خاموش باشد، دبیرخانه اخطار را از صفحه وضعیت عضو می‌فرستد"),
    )
    dues_suspend_months = models.PositiveSmallIntegerField(
        _("تعلیق پس از چند ماه از اخطار کتبی"), default=3,
        help_text=_("بند ۱.۷: عدم پرداخت حق عضویت بیش از سه ماه پس از اخطار کتبی"),
    )
    dues_auto_suspend = models.BooleanField(
        _("تعلیق خودکار پس از این مدت"), default=True,
        help_text=_("اگر خاموش باشد، این اعضا در ایمیل روزانه دبیرخانه می‌آیند تا دبیرخانه تصمیم بگیرد"),
    )
    dues_lift_on_payment = models.BooleanField(
        _("با تأیید پرداخت، تعلیقِ ناشی از بدهی خودکار رفع شود"), default=True,
    )
    suspension_max_months = models.PositiveSmallIntegerField(
        _("بیشترین مدت تعلیق (ماه)"), default=6,
        help_text=_("بند ۱.۷: تعلیق حداکثر شش ماه است و پس از آن به رفع تعلیق یا لغو عضویت می‌انجامد"),
    )
    appeal_days = models.PositiveSmallIntegerField(
        _("مهلت اعتراض (روز پس از ابلاغ)"), default=30, help_text=_("بخش ۸.۲ سند ارکان"),
    )
    reapply_after_months = models.PositiveSmallIntegerField(
        _("درخواست دوباره پس از لغو عضویت (ماه)"), default=12,
    )
    reapply_after_serious_months = models.PositiveSmallIntegerField(
        _("درخواست دوباره پس از لغو به دلیل تخلف جدی (ماه)"), default=36,
    )
    dues_text = RichTextField(
        _("راهنمای پرداخت حق عضویت در پنل (فارسی)"), blank=True,
        default="<p>مبلغ حق عضویت را به حساب زیر واریز کنید و تصویر رسید را این‌جا بفرستید. "
                "دبیرخانه پس از بررسی، پرداخت را تأیید می‌کند.</p>",
    )
    dues_text_en = RichTextField(
        _("راهنمای پرداخت حق عضویت در پنل (انگلیسی)"), blank=True,
        default="<p>Pay the membership fee into the account below and upload a photo of the receipt here. "
                "The secretariat confirms the payment once it has checked it.</p>",
    )
    suspended_text = RichTextField(
        _("متن برای عضو تعلیق‌شده یا لغوشده (فارسی)"), blank=True,
        default="<p>طبق بند ۱.۷ سند ارکان، عضو تعلیق‌شده حق رأی، استفاده از نشان و خدمات خانه را ندارد. "
                "اگر به این رأی اعتراض دارید، می‌توانید در مهلت اعتراض، اعتراض کتبی خود را به دبیر مجمع عمومی بدهید.</p>",
    )
    suspended_text_en = RichTextField(
        _("متن برای عضو تعلیق‌شده یا لغوشده (انگلیسی)"), blank=True,
        default="<p>Under section 1.7 of the governance document, a suspended member cannot vote, use the "
                "House's mark or use its services. If you disagree with this decision, you may send a written "
                "appeal to the Secretary of the General Assembly within the appeal period.</p>",
    )

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
        FieldPanel("reminder_days_before"),
        FieldPanel("max_upload_mb"),
        FieldPanel("allowed_upload_extensions"),
    ]
    certificate_panels = [
        FieldPanel("certificate_prefix"),
        FieldPanel("certificate_validity_months"),
        FieldPanel("certificate_title"), FieldPanel("certificate_title_en"),
        FieldPanel("certificate_text"), FieldPanel("certificate_text_en"),
        FieldPanel("certificate_signatory"), FieldPanel("certificate_signatory_en"),
        FieldPanel("certificate_signatory_title"), FieldPanel("certificate_signatory_title_en"),
    ]
    dues_panels = [
        FieldPanel("dues_enabled"),
        MultiFieldPanel([FieldPanel("dues_cycle"), FieldPanel("dues_start_month"), FieldPanel("dues_start_day"),
                         FieldPanel("dues_for_trial")], heading=_("سال عضویت")),
        MultiFieldPanel([FieldPanel("dues_issue_days_before"), FieldPanel("dues_payment_days"),
                         FieldPanel("dues_reminder_days_before")], heading=_("صورت‌حساب و یادآوری")),
        MultiFieldPanel([FieldPanel("dues_auto_warning"), FieldPanel("dues_suspend_months"),
                         FieldPanel("dues_auto_suspend"), FieldPanel("dues_lift_on_payment")],
                        heading=_("اخطار و تعلیق برای بدهی (بند ۱.۷)")),
        MultiFieldPanel([FieldPanel("suspension_max_months"), FieldPanel("appeal_days"),
                         FieldPanel("reapply_after_months"), FieldPanel("reapply_after_serious_months")],
                        heading=_("تعلیق، لغو و اعتراض (بندهای ۱.۷، ۱.۸ و ۸.۲)")),
        MultiFieldPanel([FieldPanel("dues_text"), FieldPanel("dues_text_en"),
                         FieldPanel("suspended_text"), FieldPanel("suspended_text_en")], heading=_("متن‌های پنل اعضا")),
    ]
    edit_handler = TabbedInterface([
        ObjectList(fee_panels, heading=_("مبالغ")),
        ObjectList(bank_panels, heading=_("حساب بانکی")),
        ObjectList(process_panels, heading=_("فرایند و مهلت‌ها")),
        ObjectList(certificate_panels, heading=_("گواهی عضویت")),
        ObjectList(dues_panels, heading=_("حق عضویت سالانه و تعلیق")),
    ])

    class Meta:
        verbose_name = _("تنظیمات عضویت")

    def clean(self):
        super().clean()
        from core.iran import clean_bank_fields

        clean_bank_fields(self)

    def application_fee_for(self, member_type):
        return getattr(self, f"application_fee_{member_type}", None)

    def annual_fee_for(self, member_type):
        return getattr(self, f"annual_fee_{member_type}", None)

    @property
    def has_bank_details(self):
        return bool(self.card_number or self.sheba)

    @property
    def upload_extensions(self):
        return [e.strip().lstrip(".").lower() for e in self.allowed_upload_extensions.split(",") if e.strip()]

    def tr(self, field):
        return BilingualMixin.tr(self, field)


@register_setting(icon="globe")
class SeoSettings(BaseGenericSetting):
    """How the site appears in search engines and when links are shared; analytics and trust badges."""

    allow_indexing = models.BooleanField(
        _("اجازه نمایش در موتورهای جستجو"), default=True,
        help_text=_("روی سرور آزمایشی خاموش کنید تا گوگل آن را فهرست نکند"),
    )
    default_description = models.TextField(
        _("توضیح پیش‌فرض سایت (فارسی)"), max_length=300, blank=True,
        default="خانه تجارت عادلانه ایران؛ شبکه تولیدکنندگان، صنعتگران و نهادهای حامی تجارت عادلانه. "
                "معرفی اعضا، فروشگاه محصولات، اخبار و عضویت.",
        help_text=_("برای صفحه‌هایی که توضیح جستجو ندارند؛ حدود ۱۵۰ نویسه"),
    )
    default_description_en = models.TextField(
        _("توضیح پیش‌فرض سایت (انگلیسی)"), max_length=300, blank=True,
        default="Fair Trade House of Iran: a network of producers, artisans and support organisations "
                "practising fair trade. Members, shop, news and membership.",
    )
    share_image = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("تصویر پیش‌فرض اشتراک‌گذاری"), null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text=_("وقتی لینک سایت در تلگرام، واتس‌اپ یا لینکدین فرستاده می‌شود؛ ترجیحاً ۱۲۰۰×۶۳۰ پیکسل"),
    )
    site_icon = models.ForeignKey(
        "wagtailimages.Image", verbose_name=_("آیکون سایت (فاوآیکون)"), null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text=_("تصویر مربعی، دست‌کم ۵۱۲×۵۱۲ پیکسل؛ در زبانه مرورگر و صفحه اصلی گوشی نمایش داده می‌شود"),
    )
    google_site_verification = models.CharField(
        _("کد تأیید گوگل سرچ کنسول"), max_length=120, blank=True,
        help_text=_("فقط مقدار content از تگ متای google-site-verification"),
    )
    bing_site_verification = models.CharField(_("کد تأیید بینگ"), max_length=120, blank=True)
    head_code = models.TextField(
        _("کد آمار بازدید"), blank=True,
        help_text=_("کد اسکریپتی که سرویس آمار (مثلاً Umami، Matomo یا گوگل آنالیتیکس) می‌دهد؛ "
                    "در همه صفحه‌های عمومی سایت در بخش head قرار می‌گیرد. فقط کد سرویس‌های مطمئن را اینجا بگذارید."),
    )
    footer_badges = models.TextField(
        _("کد نمادهای اعتماد"), blank=True,
        help_text=_("کدی که اینماد یا ساماندهی برای نمایش نماد می‌دهد؛ در پانویس همه صفحه‌ها نمایش داده می‌شود"),
    )
    robots_extra = models.TextField(
        _("قواعد اضافه robots.txt"), blank=True,
        help_text=_("در صورت نیاز؛ هر قاعده در یک خط، مثلاً Disallow: /fa/some-page/"),
    )

    panels = [
        MultiFieldPanel([FieldPanel("allow_indexing"), FieldPanel("default_description"),
                         FieldPanel("default_description_en")], heading=_("موتورهای جستجو")),
        MultiFieldPanel([FieldPanel("share_image"), FieldPanel("site_icon")], heading=_("تصویرها")),
        MultiFieldPanel([FieldPanel("google_site_verification"), FieldPanel("bing_site_verification"),
                         FieldPanel("head_code"), FieldPanel("robots_extra")], heading=_("ابزارها و آمار")),
        MultiFieldPanel([FieldPanel("footer_badges")], heading=_("نمادهای اعتماد (اینماد، ساماندهی)")),
    ]

    class Meta:
        verbose_name = _("سئو، آمار و نمادها")

    def tr(self, field):
        return BilingualMixin.tr(self, field)


@register_setting(icon="lock")
class SecuritySettings(BaseGenericSetting):
    """Content-Security-Policy and two-step sign-in for staff."""

    class CspMode(models.TextChoices):
        ENFORCE = "enforce", _("فعال (توصیه‌شده)")
        REPORT = "report", _("فقط گزارش در کنسول مرورگر (برای آزمایش)")
        OFF = "off", _("خاموش")

    class TwoFactor(models.TextChoices):
        OFF = "off", _("خاموش")
        SUPERUSERS = "superusers", _("فقط مدیران کل (superuser)")
        STAFF = "staff", _("همه کاربرانی که به پنل مدیریت دسترسی دارند")

    csp_mode = models.CharField(
        _("سیاست امنیت محتوا (CSP)"), max_length=10, choices=CspMode.choices, default=CspMode.ENFORCE,
        help_text=_("جلوی اجرای اسکریپت‌های ناشناس در صفحه‌های عمومی را می‌گیرد. اگر سرویسی (آمار، نماد، ویدیو) "
                    "پس از افزودن کار نکرد، نشانی آن را در فهرست زیر بیفزایید یا موقتاً «فقط گزارش» را بگذارید."),
    )
    csp_extra_sources = models.TextField(
        _("نشانی‌های مجاز اضافه"), blank=True,
        help_text=_("هر نشانی در یک خط، مثلاً https://stats.example.org — نشانی‌هایی که در «کد آمار بازدید» و "
                    "«کد نمادهای اعتماد» آمده‌اند خودکار مجازند."),
    )
    two_factor = models.CharField(
        _("ورود دومرحله‌ای"), max_length=12, choices=TwoFactor.choices, default=TwoFactor.OFF,
        help_text=_("پس از رمز عبور، یک کد یک‌بار مصرف به ایمیل کاربر فرستاده می‌شود. پیش از روشن کردن، مطمئن شوید "
                    "ارسال ایمیل سایت کار می‌کند و این کاربران ایمیل درست دارند."),
    )
    two_factor_remember_days = models.PositiveSmallIntegerField(
        _("به خاطر سپردن مرورگر (روز)"), default=30, validators=[MaxValueValidator(365)],
        help_text=_("پس از ورود موفق، تا این مدت از همان مرورگر کد خواسته نمی‌شود؛ ۰ یعنی هر بار کد بخواهد"),
    )
    two_factor_code_minutes = models.PositiveSmallIntegerField(
        _("اعتبار کد (دقیقه)"), default=10, validators=[MinValueValidator(2), MaxValueValidator(60)],
    )

    panels = [
        MultiFieldPanel([FieldPanel("two_factor"), FieldPanel("two_factor_remember_days"),
                         FieldPanel("two_factor_code_minutes")], heading=_("ورود دومرحله‌ای کارکنان")),
        MultiFieldPanel([FieldPanel("csp_mode"), FieldPanel("csp_extra_sources")],
                        heading=_("سیاست امنیت محتوا")),
    ]

    class Meta:
        verbose_name = _("امنیت")

    def extra_sources(self):
        from .security import origin

        return [o for o in (origin(line) for line in self.csp_extra_sources.splitlines()) if o]
