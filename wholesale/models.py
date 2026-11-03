"""
Wholesale and export enquiries (B2B), mostly from foreign buyers.

A buyer picks products and quantities on the wholesale page and leaves their
company details, country and preferred Incoterm. The enquiry goes to the
House (admin panel, e-mail, SMS) and to every producer whose products are in
it; producers answer from the member panel, and the House replies to the
buyer. No money changes hands here: this is a request for a quotation.
"""

import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList, TabbedInterface
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField
from wagtail.models import Locale, Page

from core.models import BilingualMixin, is_english

from . import email_defaults as defaults


def generate_tracking_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "W" + "".join(secrets.choice(alphabet) for _ in range(7))


def hash_ip(ip):
    if not ip:
        return ""
    return hashlib.sha256(f"{settings.SECRET_KEY}:{ip}".encode()).hexdigest()[:32]


def option_lines(text):
    """'value | Persian label' lines -> [(value, english, persian)]."""
    options = []
    for raw in (text or "").splitlines():
        if not raw.strip():
            continue
        parts = [p.strip() for p in raw.split("|")]
        value = parts[0]
        en = parts[1] if len(parts) > 1 and parts[1] else value
        fa = parts[2] if len(parts) > 2 and parts[2] else en
        options.append((value, en, fa))
    return options


@register_setting(icon="cogs")
class WholesaleSettings(BaseGenericSetting):
    """How wholesale enquiries work and the wording of their e-mails."""

    enabled = models.BooleanField(
        "پذیرش درخواست سفارش عمده", default=True,
        help_text="اگر خاموش باشد، کاتالوگ عمده دیده می‌شود اما فرم درخواست بسته است",
    )
    closed_text = models.CharField(
        "متن هنگام بسته بودن فرم (فارسی)", max_length=255, blank=True,
        default="پذیرش درخواست سفارش عمده فعلاً متوقف است. لطفاً از صفحه تماس با ما در ارتباط باشید.",
    )
    closed_text_en = models.CharField(
        "متن هنگام بسته بودن فرم (انگلیسی)", max_length=255, blank=True,
        default="We are not taking wholesale enquiries at the moment. Please get in touch through our contact page.",
    )
    incoterms = models.TextField(
        "شرایط تحویل (اینکوترمز)", blank=True, default=defaults.INCOTERMS,
        help_text="هر گزینه در یک خط: «کد | توضیح انگلیسی | توضیح فارسی»",
    )
    units = models.TextField(
        "واحدهای سفارش", blank=True, default=defaults.UNITS,
        help_text="هر واحد در یک خط: «کد | انگلیسی | فارسی». واحد اول پیش‌فرض است.",
    )
    extra_recipients = models.CharField(
        "ایمیل‌های دیگر برای اعلان", max_length=500, blank=True,
        help_text="افزون بر کاربرانی که اجازه رسیدگی به سفارش‌های عمده را دارند (گروه‌های «دبیرخانه» و "
                  "«کارگروه توسعه بازار»). چند نشانی را با ویرگول جدا کنید.",
    )
    notify_producers = models.BooleanField(
        "خبر دادن خودکار به تولیدکنندگان", default=True,
        help_text="با هر درخواست، به تولیدکنندگانی که محصولشان در آن است ایمیل و پیامک فرستاده می‌شود و "
                  "درخواست در پنل اعضای آن‌ها دیده می‌شود. اگر خاموش باشد، دبیرخانه خودش از پنل مدیریت ارجاع می‌دهد.",
    )
    share_buyer_contact = models.BooleanField(
        "نمایش نام و راه تماس خریدار به تولیدکننده", default=False,
        help_text="اگر خاموش باشد، تولیدکننده فقط کشور، محصولات و شرایط را می‌بیند و ارتباط با خریدار از راه خانه است",
    )
    min_seconds = models.PositiveSmallIntegerField(
        "کمترین زمان پر کردن فرم (ثانیه)", default=4,
        help_text="فرمی که سریع‌تر از این فرستاده شود، کار ربات حساب می‌شود",
    )
    max_per_hour = models.PositiveSmallIntegerField(
        "بیشترین درخواست از یک نشانی اینترنتی در ساعت", default=5,
    )
    max_lines = models.PositiveSmallIntegerField("بیشترین تعداد محصول در یک درخواست", default=40)

    buyer_subject = models.CharField("موضوع ایمیل به خریدار (فارسی)", max_length=200, default=defaults.BUYER_SUBJECT)
    buyer_body = models.TextField("متن ایمیل به خریدار (فارسی)", default=defaults.BUYER_BODY,
                                  help_text=defaults.PLACEHOLDERS_HELP)
    buyer_subject_en = models.CharField("موضوع ایمیل به خریدار (انگلیسی)", max_length=200,
                                        default=defaults.BUYER_SUBJECT_EN)
    buyer_body_en = models.TextField("متن ایمیل به خریدار (انگلیسی)", default=defaults.BUYER_BODY_EN,
                                     help_text=defaults.PLACEHOLDERS_HELP)
    producer_subject = models.CharField("موضوع ایمیل به تولیدکننده", max_length=200,
                                        default=defaults.PRODUCER_SUBJECT)
    producer_body = models.TextField("متن ایمیل به تولیدکننده", default=defaults.PRODUCER_BODY,
                                     help_text=defaults.PRODUCER_PLACEHOLDERS_HELP)

    edit_handler = TabbedInterface([
        ObjectList([
            FieldPanel("enabled"), FieldPanel("closed_text"), FieldPanel("closed_text_en"),
            FieldPanel("incoterms"), FieldPanel("units"), FieldPanel("max_lines"),
        ], heading="فرم"),
        ObjectList([
            FieldPanel("extra_recipients"), FieldPanel("notify_producers"), FieldPanel("share_buyer_contact"),
        ], heading="ارجاع"),
        ObjectList([
            MultiFieldPanel([FieldPanel("buyer_subject_en"), FieldPanel("buyer_body_en"),
                             FieldPanel("buyer_subject"), FieldPanel("buyer_body")], heading="رسید برای خریدار"),
            MultiFieldPanel([FieldPanel("producer_subject"), FieldPanel("producer_body")], heading="خبر به تولیدکننده"),
        ], heading="ایمیل‌ها"),
        ObjectList([FieldPanel("min_seconds"), FieldPanel("max_per_hour")], heading="ضد هرزنامه"),
    ])

    class Meta:
        verbose_name = "تنظیمات سفارش عمده"

    def tr(self, field):
        return BilingualMixin.tr(self, field)

    def incoterm_choices(self, en=None):
        en = is_english() if en is None else en
        choices = []
        for value, label_en, label_fa in option_lines(self.incoterms):
            label = label_en if en else label_fa
            choices.append((value, value if label == value else f"{value} – {label}"))
        return choices

    def unit_choices(self, en=None):
        en = is_english() if en is None else en
        return [(value, label_en if en else label_fa) for value, label_en, label_fa in option_lines(self.units)]

    def unit_label(self, value, en=False):
        return dict(self.unit_choices(en)).get(value, value)


class WholesalePage(Page):
    """The wholesale catalogue and enquiry form; one per language."""

    intro = RichTextField("متن بالای کاتالوگ", blank=True)
    form_intro = RichTextField("متن بالای مشخصات خریدار", blank=True)
    thank_you_text = RichTextField("متن پس از ارسال", blank=True)
    side_note = RichTextField(
        "توضیح کنار فرم", blank=True,
        help_text="مثلاً کمترین مقدار سفارش، زمان آماده‌سازی، بسته‌بندی صادراتی و این‌که پاسخ چه زمانی می‌رسد",
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"), FieldPanel("form_intro"), FieldPanel("side_note"), FieldPanel("thank_you_text"),
    ]
    max_count_per_parent = 1
    subpage_types = []
    template = "wholesale/wholesale_page.html"

    class Meta:
        verbose_name = "صفحه سفارش عمده و صادرات"

    @classmethod
    def for_active_locale(cls):
        return cls.objects.live().filter(locale=Locale.get_active()).first()

    def serve(self, request, *args, **kwargs):
        from .views import serve_wholesale_page

        return serve_wholesale_page(self, request)


class WholesaleInquiry(ClusterableModel):
    class BuyerType(models.TextChoices):
        IMPORTER = "importer", "واردکننده یا توزیع‌کننده"
        RETAILER = "retailer", "فروشگاه خرده‌فروشی"
        FAIRTRADE = "fairtrade", "سازمان یا فروشگاه تجارت عادلانه"
        ONLINE = "online", "فروشگاه اینترنتی"
        CORPORATE = "corporate", "هدیه سازمانی"
        OTHER = "other", "سایر"

    BUYER_TYPE_EN = {
        "importer": "Importer or distributor", "retailer": "Retail shop",
        "fairtrade": "Fair trade organisation or shop", "online": "Online shop",
        "corporate": "Corporate gifts", "other": "Other",
    }

    class Status(models.TextChoices):
        NEW = "new", "تازه"
        REVIEWING = "reviewing", "در حال بررسی"
        QUOTED = "quoted", "پیشنهاد قیمت به خریدار فرستاده شد"
        ORDERED = "ordered", "سفارش قطعی شد"
        CLOSED = "closed", "بسته شد بی‌نتیجه"
        SPAM = "spam", "هرزنامه"

    tracking_code = models.CharField("کد پیگیری", max_length=12, unique=True, default=generate_tracking_code,
                                     editable=False)
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)
    language = models.CharField("زبان فرم", max_length=5, default="en", editable=False)
    ip_hash = models.CharField(max_length=64, blank=True, editable=False, db_index=True)

    company = models.CharField("شرکت یا سازمان", max_length=200)
    contact_name = models.CharField("نام فرد رابط", max_length=200)
    email = models.EmailField("ایمیل")
    phone = models.CharField("تلفن یا واتس‌اپ", max_length=40, blank=True)
    country = models.CharField("کشور", max_length=80)
    city = models.CharField("شهر", max_length=80, blank=True)
    website = models.CharField("وب‌سایت", max_length=200, blank=True)
    buyer_type = models.CharField("نوع خریدار", max_length=20, choices=BuyerType.choices, default=BuyerType.IMPORTER)

    incoterm = models.CharField("شرایط تحویل (اینکوترمز)", max_length=60, blank=True)
    destination = models.CharField("بندر یا شهر مقصد", max_length=160, blank=True)
    needed_by = models.CharField("زمان مورد نیاز", max_length=120, blank=True)
    other_products = models.TextField("محصولات دیگر یا سفارش سفارشی", blank=True)
    message = models.TextField("توضیحات خریدار", blank=True)

    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.NEW)
    house_notes = models.TextField("یادداشت‌های خانه", blank=True,
                                   help_text="فقط کارکنان خانه این یادداشت را می‌بینند، نه خریدار و نه تولیدکننده")

    class Meta:
        verbose_name = "درخواست سفارش عمده"
        verbose_name_plural = "درخواست‌های سفارش عمده"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tracking_code} – {self.company} ({self.country})"

    @property
    def buyer_type_display(self):
        return self.BUYER_TYPE_EN.get(self.buyer_type, self.buyer_type) if is_english() else self.get_buyer_type_display()

    @property
    def line_count(self):
        return self.lines.count()

    def admin_url(self):
        return reverse("wholesale_inquiries:edit", args=[self.pk])


class WholesaleInquiryLine(models.Model):
    inquiry = ParentalKey(WholesaleInquiry, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("products.Product", verbose_name="محصول", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="wholesale_lines")
    member = models.ForeignKey("members.Member", verbose_name="تولیدکننده", null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="wholesale_lines")
    product_name = models.CharField("نام محصول", max_length=200,
                                    help_text="هنگام ثبت از محصول برداشته می‌شود تا اگر محصول حذف شد، بماند")
    quantity = models.PositiveIntegerField("مقدار")
    unit = models.CharField("واحد", max_length=20, blank=True)
    note = models.CharField("توضیح", max_length=255, blank=True)

    panels = [FieldPanel("product"), FieldPanel("member"), FieldPanel("product_name"),
              FieldPanel("quantity"), FieldPanel("unit"), FieldPanel("note")]

    class Meta:
        verbose_name = "قلم سفارش"
        verbose_name_plural = "اقلام سفارش"
        ordering = ["pk"]

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"

    @property
    def unit_display(self):
        return WholesaleSettings.load().unit_label(self.unit, en=is_english())


class ProducerShare(models.Model):
    """One producer's part in an enquiry: what they see in the member panel and their answer."""

    class Status(models.TextChoices):
        NEW = "new", "هنوز دیده نشده"
        SEEN = "seen", "دیده شد"
        QUOTED = "quoted", "می‌تواند تأمین کند"
        PARTLY = "partly", "بخشی را می‌تواند تأمین کند"
        DECLINED = "declined", "نمی‌تواند تأمین کند"

    STATUS_EN = {"new": "Not opened yet", "seen": "Opened", "quoted": "Can supply",
                 "partly": "Can supply part of it", "declined": "Cannot supply"}
    ANSWERED = ("quoted", "partly", "declined")

    inquiry = ParentalKey(WholesaleInquiry, on_delete=models.CASCADE, related_name="producers")
    member = models.ForeignKey("members.Member", verbose_name="تولیدکننده", on_delete=models.CASCADE,
                               related_name="wholesale_shares")
    status = models.CharField("پاسخ تولیدکننده", max_length=20, choices=Status.choices, default=Status.NEW)
    price_quote = models.CharField("قیمت پیشنهادی", max_length=255, blank=True,
                                   help_text="قیمت واحد و ارز، یا جمع کل")
    lead_time = models.CharField("زمان آماده‌سازی", max_length=120, blank=True)
    reply = models.TextField("توضیح تولیدکننده", blank=True)
    replied_at = models.DateTimeField("زمان پاسخ", null=True, blank=True)
    replied_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="پاسخ‌دهنده", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    notified_at = models.DateTimeField("زمان خبر دادن", null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [FieldPanel("member"), FieldPanel("status"), FieldPanel("price_quote"),
              FieldPanel("lead_time"), FieldPanel("reply")]

    class Meta:
        verbose_name = "ارجاع به تولیدکننده"
        verbose_name_plural = "ارجاع به تولیدکنندگان"
        ordering = ["pk"]
        constraints = [models.UniqueConstraint(fields=["inquiry", "member"], name="wholesale_share_unique")]

    def __str__(self):
        return f"{self.inquiry.tracking_code} – {self.member}"

    @property
    def status_display(self):
        return self.STATUS_EN.get(self.status, self.status) if is_english() else self.get_status_display()

    @property
    def is_answered(self):
        return self.status in self.ANSWERED

    def lines(self):
        """The lines for this producer's products; all lines if the House referred the whole enquiry."""
        own = self.inquiry.lines.filter(member=self.member)
        return own if own.exists() else self.inquiry.lines.all()
