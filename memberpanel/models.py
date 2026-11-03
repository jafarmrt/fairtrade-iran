"""
Settings of the member panel, where members edit their own profile and
products. Everything here is edited in the admin panel (Settings → پنل اعضا).
"""

from django.conf import settings
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList, TabbedInterface
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField

from core.models import BilingualMixin


@register_setting(icon="user")
class PanelSettings(BaseGenericSetting):
    enabled = models.BooleanField(
        "پنل اعضا فعال است", default=True,
        help_text="اگر خاموش باشد، اعضا نمی‌توانند وارد پنل شوند (کارکنان همچنان از بخش مدیریت کار می‌کنند)",
    )

    # ---- texts ----
    welcome = RichTextField("متن خوشامد پنل (فارسی)", blank=True,
                            default="<p>از اینجا معرفی مجموعه و محصولات خود را در سایت خانه به‌روز کنید.</p>")
    welcome_en = RichTextField("متن خوشامد پنل (انگلیسی)", blank=True,
                               default="<p>Keep your profile and products on the House's website up to date from here.</p>")
    login_intro = RichTextField(
        "توضیح صفحه ورود (فارسی)", blank=True,
        default="<p>حساب کاربری پنل را دبیرخانه پس از پذیرش عضویت برای شما می‌سازد. اگر رمز ندارید، "
                "از «فراموشی رمز» با ایمیلی که به دبیرخانه داده‌اید رمز بسازید.</p>",
    )
    login_intro_en = RichTextField(
        "توضیح صفحه ورود (انگلیسی)", blank=True,
        default="<p>The secretariat creates your panel account once your membership is accepted. If you have "
                "no password yet, use \"Forgot password\" with the e-mail address you gave the secretariat.</p>",
    )
    help_text = RichTextField("راهنمای پنل (فارسی)", blank=True,
                              help_text="در کنار فرم‌های پنل نمایش داده می‌شود؛ مثلاً راهنمای عکاسی از محصول")
    help_text_en = RichTextField("راهنمای پنل (انگلیسی)", blank=True)

    # ---- products ----
    new_products_need_review = models.BooleanField(
        "محصولات تازه پیش از نمایش بررسی شوند", default=True,
        help_text="اگر روشن باشد، محصولی که عضو می‌سازد تا تأیید کارکنان (برداشتن تیک «در انتظار بررسی») در سایت دیده نمی‌شود",
    )
    max_products = models.PositiveSmallIntegerField(
        "بیشترین تعداد محصول برای هر عضو", default=50, help_text="۰ یعنی بدون محدودیت",
    )
    max_images_per_product = models.PositiveSmallIntegerField("بیشترین تعداد تصویر هر محصول", default=6)
    allow_delete_products = models.BooleanField(
        "اعضا بتوانند محصول را حذف کنند", default=True,
        help_text="اگر خاموش باشد، اعضا فقط می‌توانند محصول را از نمایش خارج کنند",
    )
    review_email = models.EmailField(
        "ایمیل اطلاع‌رسانی محصولات تازه", blank=True,
        help_text="محصولی که در انتظار بررسی است به این نشانی خبر داده می‌شود؛ "
                  "اگر خالی باشد، ایمیل اطلاع‌رسانی تنظیمات سایت استفاده می‌شود",
    )

    # ---- profiles from the membership workflow ----
    create_profile_on_trial = models.BooleanField(
        "با پذیرش آزمایشی، پروفایل عضو خودکار ساخته شود", default=True,
        help_text="اطلاعات از پرونده عضویت برداشته می‌شود و وضعیت «عضو آزمایشی» می‌گیرد",
    )
    publish_new_profiles = models.BooleanField(
        "پروفایل‌های خودکار بلافاصله در سایت نمایش داده شوند", default=False,
        help_text="اگر خاموش باشد، کارکنان پس از بازبینی «نمایش در سایت» را روشن می‌کنند",
    )
    sms_login = models.BooleanField(
        "ورود با کد پیامکی", default=False,
        help_text="اعضا با شماره موبایلی که در «شماره‌های موبایل ورود» ثبت شده، بدون رمز و با کد یک‌بارمصرف وارد پنل "
                  "می‌شوند. ارسال پیامک هم باید در «تنظیمات پیامک» روشن باشد. متن پیامک در «متن‌های پیامک» است.",
    )
    sms_code_minutes = models.PositiveSmallIntegerField("اعتبار کد ورود (دقیقه)", default=5)
    invite_new_members = models.BooleanField(
        "برای عضو تازه حساب پنل ساخته و ایمیل دعوت فرستاده شود", default=True,
        help_text="متن ایمیل در «قالب‌های ایمیل عضویت» (دعوت به پنل اعضا) ویرایش می‌شود",
    )

    edit_handler = TabbedInterface([
        ObjectList([
            FieldPanel("enabled"),
            MultiFieldPanel([FieldPanel("welcome"), FieldPanel("welcome_en")], heading="خوشامد"),
            MultiFieldPanel([FieldPanel("login_intro"), FieldPanel("login_intro_en")], heading="صفحه ورود"),
            MultiFieldPanel([FieldPanel("help_text"), FieldPanel("help_text_en")], heading="راهنما"),
        ], heading="عمومی و متن‌ها"),
        ObjectList([
            FieldPanel("new_products_need_review"),
            FieldPanel("review_email"),
            FieldPanel("max_products"),
            FieldPanel("max_images_per_product"),
            FieldPanel("allow_delete_products"),
        ], heading="محصولات"),
        ObjectList([
            FieldPanel("create_profile_on_trial"),
            FieldPanel("publish_new_profiles"),
            FieldPanel("invite_new_members"),
        ], heading="اعضای تازه"),
        ObjectList([
            FieldPanel("sms_login"),
            FieldPanel("sms_code_minutes"),
        ], heading="ورود با پیامک"),
    ])

    class Meta:
        verbose_name = "پنل اعضا"

    def tr(self, field):
        return BilingualMixin.tr(self, field)


class LoginMobile(models.Model):
    """The mobile number a panel user signs in with by SMS code (one number per user, one user per number)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name="کاربر", on_delete=models.CASCADE,
                                related_name="login_mobile")
    mobile = models.CharField("شماره موبایل", max_length=11, unique=True, help_text="مثل ۰۹۱۲۳۴۵۶۷۸۹")
    verified_at = models.DateTimeField("تأیید با کد پیامکی", null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [FieldPanel("user"), FieldPanel("mobile")]

    class Meta:
        verbose_name = "شماره موبایل ورود"
        verbose_name_plural = "شماره‌های موبایل ورود"
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user} · {self.mobile}"

    def clean(self):
        from django.core.exceptions import ValidationError

        from core.iran import clean_mobile

        try:
            self.mobile = clean_mobile(self.mobile)
        except ValidationError as e:
            raise ValidationError({"mobile": e.messages})
        if not self.mobile:
            raise ValidationError({"mobile": "شماره موبایل را بنویسید."})
