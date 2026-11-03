"""
Membership applications, following the admission process in section 1.4 of
the governance document (سند ارکان، نسخه ۲):

    application + fee -> secretariat check (7 days) -> commission evaluation
    (30 days, field visit for producers) -> trial / request fix / reasoned
    rejection -> 3-month trial -> full member / one-off extension / not
    accepted -> secretariat registers the member and issues a certificate.

Deadlines, fees, texts, form questions and e-mails are all editable in the
admin panel (MembershipSettings, the membership page, snippets).
"""

import calendar
import datetime
import os
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page
from wagtail.search import index

from archive.storage import PrivateStorage
from core.blocks import BodyBlock
from core.models import BilingualMixin, is_english

# ---------------------------------------------------------------------------
# Member types and statuses
# ---------------------------------------------------------------------------


class MemberType(models.TextChoices):
    # The values match the field suffixes in core.MembershipSettings
    # (application_fee_producer, annual_fee_producer, ...).
    PRODUCER = "producer", "تولیدکننده"
    INSTITUTION = "institution", "نهاد حمایتی"
    NETWORK = "network", "شبکه تجارت عادلانه"
    INDIVIDUAL = "individual", "فرد حامی"


MEMBER_TYPE_EN = {
    MemberType.PRODUCER: "Producer",
    MemberType.INSTITUTION: "Support institution",
    MemberType.NETWORK: "Fair trade network",
    MemberType.INDIVIDUAL: "Individual supporter",
}


def member_type_label(code):
    if is_english():
        return MEMBER_TYPE_EN.get(code, code)
    try:
        return MemberType(code).label
    except ValueError:
        return code


class Status(models.TextChoices):
    SUBMITTED = "submitted", "در انتظار کنترل مدارک دبیرخانه"
    INCOMPLETE = "incomplete", "نقص مدارک (منتظر متقاضی)"
    COMMISSION = "commission", "در حال ارزیابی کمیسیون"
    FIX_REQUESTED = "fix_requested", "درخواست اصلاح (منتظر متقاضی)"
    REJECTED = "rejected", "رد مستدل"
    TRIAL = "trial", "عضو آزمایشی"
    TRIAL_EXTENDED = "trial_extended", "عضو آزمایشی (تمدیدشده)"
    NOT_ACCEPTED = "not_accepted", "عدم پذیرش پس از دوره آزمایشی"
    APPROVED = "approved", "تأیید عضویت رسمی (در انتظار ثبت)"
    MEMBER = "member", "عضو رسمی"
    WITHDRAWN = "withdrawn", "بایگانی‌شده"


STATUS_EN = {
    Status.SUBMITTED: "Received, documents being checked by the secretariat",
    Status.INCOMPLETE: "Documents incomplete, waiting for you",
    Status.COMMISSION: "Under evaluation by the Supervisory Commission",
    Status.FIX_REQUESTED: "Changes requested, waiting for you",
    Status.REJECTED: "Rejected (with reasons)",
    Status.TRIAL: "Trial member",
    Status.TRIAL_EXTENDED: "Trial member (extended)",
    Status.NOT_ACCEPTED: "Not accepted after the trial period",
    Status.APPROVED: "Approved as full member, registration in progress",
    Status.MEMBER: "Full member",
    Status.WITHDRAWN: "Archived",
}

# Statuses where the file is closed and needs nothing more.
CLOSED_STATUSES = {Status.REJECTED, Status.NOT_ACCEPTED, Status.MEMBER, Status.WITHDRAWN}
# Statuses where the applicant can send more documents from the tracking page.
WAITING_FOR_APPLICANT = {Status.INCOMPLETE, Status.FIX_REQUESTED}


def status_label(code):
    if is_english():
        return STATUS_EN.get(code, code)
    try:
        return Status(code).label
    except ValueError:
        return code


def add_months(day, months):
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    return datetime.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


# ---------------------------------------------------------------------------
# Private storage for application files
# ---------------------------------------------------------------------------


class ApplicationStorage(PrivateStorage):
    """PRIVATE_MEDIA_ROOT/membership/, with no public URL; served only by a staff-checked view."""

    def __init__(self):
        super().__init__("membership")

    def url(self, name):
        raise ValueError("Private files have no public URL.")


def private_storage():
    return ApplicationStorage()


def application_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()[:10]
    return f"{instance.application.tracking_code}/{uuid.uuid4().hex}{ext}"


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

TRACKING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_tracking_code():
    while True:
        code = "FT-" + "".join(secrets.choice(TRACKING_ALPHABET) for _ in range(8))
        if not MembershipApplication.objects.filter(tracking_code=code).exists():
            return code


class MembershipApplication(models.Model):
    tracking_code = models.CharField("کد پیگیری", max_length=20, unique=True, editable=False)
    member_type = models.CharField("نوع عضویت", max_length=20, choices=MemberType.choices)
    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    deadline = models.DateField("مهلت اقدام", null=True, blank=True, db_index=True)
    status_changed_at = models.DateTimeField("تاریخ آخرین تغییر وضعیت", default=timezone.now)
    language = models.CharField("زبان متقاضی", max_length=5, default="fa")

    name = models.CharField("نام متقاضی / مجموعه", max_length=200)
    name_en = models.CharField("نام انگلیسی", max_length=200, blank=True)
    contact_person = models.CharField("نام رابط", max_length=150, blank=True)
    email = models.EmailField("ایمیل")
    phone = models.CharField("تلفن", max_length=40)
    city = models.CharField("استان و شهر", max_length=150, blank=True)
    address = models.TextField("نشانی", blank=True)
    website = models.CharField("وب‌سایت یا شبکه اجتماعی", max_length=300, blank=True)
    referred_by = models.CharField("معرف", max_length=200, blank=True)

    answers = models.JSONField("پاسخ‌ها", default=list, blank=True)

    fee_amount = models.PositiveBigIntegerField("هزینه درخواست هنگام ثبت (ریال)", null=True, blank=True)
    payment_reference = models.CharField("شماره پیگیری پرداخت", max_length=100, blank=True)
    fee_confirmed_at = models.DateTimeField("تأیید دریافت هزینه", null=True, blank=True)

    agreed_principles = models.BooleanField("تعهد به اصول ده‌گانه", default=False)
    agreed_inspections = models.BooleanField("پذیرش بازرسی‌ها", default=False)

    field_visit_date = models.DateField("تاریخ بازدید میدانی", null=True, blank=True)
    field_visit_report = models.TextField("گزارش بازدید میدانی", blank=True)

    trial_starts_on = models.DateField("شروع دوره آزمایشی", null=True, blank=True)
    trial_ends_on = models.DateField("پایان دوره آزمایشی", null=True, blank=True)

    submitted_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "درخواست عضویت"
        verbose_name_plural = "درخواست‌های عضویت"
        ordering = ["-submitted_at"]
        permissions = [
            ("secretariat_actions", "اقدامات دبیرخانه روی پرونده عضویت"),
            ("commission_actions", "ثبت رأی کمیسیون روی پرونده عضویت"),
        ]

    def __str__(self):
        return f"{self.tracking_code} | {self.name}"

    def save(self, *args, **kwargs):
        if not self.tracking_code:
            self.tracking_code = new_tracking_code()
        super().save(*args, **kwargs)

    # ---- display helpers ----

    @property
    def member_type_display(self):
        return member_type_label(self.member_type)

    @property
    def status_display(self):
        return status_label(self.status)

    @property
    def is_producer(self):
        return self.member_type == MemberType.PRODUCER

    @property
    def is_closed(self):
        return self.status in CLOSED_STATUSES

    @property
    def is_overdue(self):
        return bool(self.deadline and self.deadline < timezone.localdate() and not self.is_closed)

    @property
    def days_left(self):
        if not self.deadline:
            return None
        return (self.deadline - timezone.localdate()).days

    @property
    def fee_confirmed(self):
        return self.fee_confirmed_at is not None

    @property
    def fee_required(self):
        return bool(self.fee_amount)

    @property
    def was_extended(self):
        return self.events.filter(to_status=Status.TRIAL_EXTENDED).exists()

    @property
    def certificate_or_none(self):
        return Certificate.objects.filter(application=self).first()

    def public_events(self):
        return self.events.exclude(message="").order_by("created_at")


class ApplicationDocument(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = "receipt", "رسید پرداخت"
        ANSWER = "answer", "پاسخ پرسش فرم"
        ADDITIONAL = "additional", "مدرک تکمیلی"

    application = models.ForeignKey(MembershipApplication, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField("نوع", max_length=20, choices=Kind.choices, default=Kind.ADDITIONAL)
    label = models.CharField("عنوان", max_length=255, blank=True)
    file = models.FileField("فایل", storage=private_storage, upload_to=application_upload_to, max_length=255)
    original_name = models.CharField("نام اصلی فایل", max_length=255, blank=True)
    uploaded_at = models.DateTimeField("تاریخ بارگذاری", auto_now_add=True)

    class Meta:
        verbose_name = "مدرک پیوست"
        verbose_name_plural = "مدارک پیوست"
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.label or self.original_name


class ApplicationEvent(models.Model):
    """One line in the file's history: a status change or a note."""

    application = models.ForeignKey(MembershipApplication, on_delete=models.CASCADE, related_name="events")
    created_at = models.DateTimeField("تاریخ", default=timezone.now)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="کاربر", null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="+")
    action = models.CharField("اقدام", max_length=40)
    from_status = models.CharField("وضعیت قبلی", max_length=20, blank=True)
    to_status = models.CharField("وضعیت جدید", max_length=20, blank=True)
    message = models.TextField("پیام به متقاضی", blank=True)
    internal_note = models.TextField("یادداشت داخلی", blank=True)
    decision_reference = models.CharField("شماره/تاریخ صورتجلسه", max_length=200, blank=True)

    class Meta:
        verbose_name = "رویداد پرونده"
        verbose_name_plural = "رویدادهای پرونده"
        ordering = ["created_at"]

    @property
    def to_status_display(self):
        return status_label(self.to_status) if self.to_status else ""


# ---------------------------------------------------------------------------
# Editable form questions and e-mails
# ---------------------------------------------------------------------------


class ApplicationQuestion(BilingualMixin, models.Model):
    class FieldType(models.TextChoices):
        TEXT = "text", "متن کوتاه"
        TEXTAREA = "textarea", "متن بلند"
        NUMBER = "number", "عدد"
        EMAIL = "email", "ایمیل"
        URL = "url", "نشانی وب"
        DATE = "date", "تاریخ"
        SELECT = "select", "انتخاب از فهرست"
        CHECKBOX = "checkbox", "تیک (بله/خیر)"
        FILE = "file", "بارگذاری فایل"

    label = models.CharField("پرسش (فارسی)", max_length=255)
    label_en = models.CharField("پرسش (انگلیسی)", max_length=255, blank=True)
    help_text = models.CharField("راهنما (فارسی)", max_length=500, blank=True)
    help_text_en = models.CharField("راهنما (انگلیسی)", max_length=500, blank=True)
    field_type = models.CharField("نوع پاسخ", max_length=20, choices=FieldType.choices, default=FieldType.TEXT)
    choices = models.TextField("گزینه‌ها (فارسی)", blank=True, help_text="برای «انتخاب از فهرست»: هر گزینه در یک خط")
    choices_en = models.TextField("گزینه‌ها (انگلیسی)", blank=True, help_text="به همان ترتیب گزینه‌های فارسی")
    required = models.BooleanField("پاسخ اجباری است", default=True)

    for_producer = models.BooleanField("تولیدکننده", default=False)
    for_institution = models.BooleanField("نهاد حمایتی", default=False)
    for_network = models.BooleanField("شبکه تجارت عادلانه", default=False)
    for_individual = models.BooleanField("فرد حامی", default=False)

    sort_order = models.PositiveIntegerField("ترتیب", default=0, help_text="عدد کوچک‌تر بالاتر نمایش داده می‌شود")
    active = models.BooleanField("فعال", default=True)

    panels = [
        MultiFieldPanel([FieldPanel("label"), FieldPanel("label_en"), FieldPanel("help_text"),
                         FieldPanel("help_text_en")], heading="متن پرسش"),
        MultiFieldPanel([FieldPanel("field_type"), FieldPanel("required"), FieldPanel("choices"),
                         FieldPanel("choices_en")], heading="نوع پاسخ"),
        MultiFieldPanel([FieldPanel("for_producer"), FieldPanel("for_institution"), FieldPanel("for_network"),
                         FieldPanel("for_individual")], heading="برای کدام نوع عضویت پرسیده شود؟"),
        MultiFieldPanel([FieldPanel("sort_order"), FieldPanel("active")], heading="نمایش"),
    ]

    class Meta:
        verbose_name = "پرسش فرم عضویت"
        verbose_name_plural = "پرسش‌های فرم عضویت"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.label

    @classmethod
    def for_type(cls, member_type):
        return cls.objects.filter(active=True, **{f"for_{member_type}": True})

    def types_display(self):
        return "، ".join(t.label for t in MemberType if getattr(self, f"for_{t.value}"))

    types_display.short_description = "نوع عضویت"

    def choice_list(self):
        fa = [c.strip() for c in self.choices.splitlines() if c.strip()]
        en = [c.strip() for c in self.choices_en.splitlines() if c.strip()]
        if is_english() and len(en) == len(fa):
            return list(zip(fa, en))
        return list(zip(fa, fa))


class EmailTemplate(models.Model):
    class Event(models.TextChoices):
        RECEIVED = "received", "به متقاضی: درخواست دریافت شد"
        STAFF_NEW = "staff_new", "به دبیرخانه: درخواست تازه"
        STAFF_RESUBMITTED = "staff_resubmitted", "به دبیرخانه/کمیسیون: متقاضی مدارک تکمیلی فرستاد"
        COMMISSION_NEW = "commission_new", "به کمیسیون: پرونده برای ارزیابی ارسال شد"
        STAFF_REMINDER = "staff_reminder", "به دبیرخانه/کمیسیون: یادآوری مهلت‌ها"
        STATUS_INCOMPLETE = "status_incomplete", "به متقاضی: نقص مدارک"
        STATUS_COMMISSION = "status_commission", "به متقاضی: ارسال به کمیسیون"
        STATUS_FIX_REQUESTED = "status_fix_requested", "به متقاضی: درخواست اصلاح"
        STATUS_REJECTED = "status_rejected", "به متقاضی: رد مستدل"
        STATUS_TRIAL = "status_trial", "به متقاضی: پذیرش آزمایشی"
        STATUS_TRIAL_EXTENDED = "status_trial_extended", "به متقاضی: تمدید دوره آزمایشی"
        STATUS_NOT_ACCEPTED = "status_not_accepted", "به متقاضی: عدم پذیرش پس از دوره آزمایشی"
        STATUS_APPROVED = "status_approved", "به متقاضی: تأیید عضویت رسمی"
        STATUS_MEMBER = "status_member", "به متقاضی: ثبت عضویت و صدور گواهی"
        STATUS_WITHDRAWN = "status_withdrawn", "به متقاضی: بایگانی پرونده"
        PANEL_INVITE = "panel_invite", "به عضو تازه: دعوت به پنل اعضا"
        PANEL_PRODUCT_REVIEW = "panel_product_review", "به کارکنان: محصول تازه از پنل اعضا در انتظار بررسی"

    event = models.CharField("رویداد", max_length=40, choices=Event.choices, unique=True)
    active = models.BooleanField("ارسال شود", default=True)
    subject = models.CharField("موضوع (فارسی)", max_length=200)
    subject_en = models.CharField("موضوع (انگلیسی)", max_length=200, blank=True)
    body = models.TextField(
        "متن (فارسی)",
        help_text="می‌توانید از این‌ها استفاده کنید: {name} {code} {type} {status} {deadline} {message} "
                  "{track_url} {admin_url} {certificate_number} {certificate_url} {site_name} {list}؛ "
                  "برای ایمیل‌های پنل اعضا: {name} {username} {set_password_url} {panel_url} {product} {member} {admin_url} {site_name}",
    )
    body_en = models.TextField("متن (انگلیسی)", blank=True)

    panels = [
        FieldPanel("event"), FieldPanel("active"),
        MultiFieldPanel([FieldPanel("subject"), FieldPanel("body")], heading="فارسی"),
        MultiFieldPanel([FieldPanel("subject_en"), FieldPanel("body_en")], heading="انگلیسی"),
    ]

    class Meta:
        verbose_name = "قالب ایمیل عضویت"
        verbose_name_plural = "قالب‌های ایمیل عضویت"
        ordering = ["event"]

    def __str__(self):
        return self.get_event_display()


# ---------------------------------------------------------------------------
# Certificates
# ---------------------------------------------------------------------------


class Certificate(BilingualMixin, models.Model):
    application = models.OneToOneField(MembershipApplication, verbose_name="پرونده", on_delete=models.PROTECT,
                                       related_name="certificate", null=True, blank=True)
    number = models.CharField("شماره گواهی", max_length=40, unique=True)
    name = models.CharField("نام عضو (فارسی)", max_length=200)
    name_en = models.CharField("نام عضو (انگلیسی)", max_length=200, blank=True)
    member_type = models.CharField("نوع عضویت", max_length=20, choices=MemberType.choices)
    issued_on = models.DateField("تاریخ صدور", default=timezone.localdate)
    valid_until = models.DateField("اعتبار تا", null=True, blank=True)
    revoked = models.BooleanField("باطل شده", default=False)
    revoked_reason = models.CharField("دلیل ابطال", max_length=300, blank=True)

    panels = [
        FieldPanel("number", read_only=True),
        FieldPanel("name"), FieldPanel("name_en"), FieldPanel("member_type"),
        FieldPanel("issued_on"), FieldPanel("valid_until"),
        MultiFieldPanel([FieldPanel("revoked"), FieldPanel("revoked_reason")], heading="ابطال (تعلیق یا لغو عضویت)"),
    ]

    class Meta:
        verbose_name = "گواهی عضویت"
        verbose_name_plural = "گواهی‌های عضویت"
        ordering = ["-issued_on", "-id"]

    def __str__(self):
        return f"{self.number} | {self.name}"

    @property
    def member_type_display(self):
        return member_type_label(self.member_type)

    @property
    def is_expired(self):
        return bool(self.valid_until and self.valid_until < timezone.localdate())

    @property
    def is_valid(self):
        return not self.revoked and not self.is_expired

    @classmethod
    def next_number(cls, prefix, year):
        base = f"{prefix}-{year}-"
        n = cls.objects.filter(number__startswith=base).count() + 1
        while cls.objects.filter(number=f"{base}{n:04d}").exists():
            n += 1
        return f"{base}{n:04d}"


# ---------------------------------------------------------------------------
# The public membership page
# ---------------------------------------------------------------------------


class ProcessStepBlock(blocks.StructBlock):
    title = blocks.CharBlock(label="عنوان مرحله")
    text = blocks.TextBlock(
        label="توضیح", required=False,
        help_text="{secretariat_days}، {commission_days} و {trial_months} با عددهای تنظیمات عضویت جایگزین می‌شوند",
    )

    class Meta:
        icon = "list-ol"
        label = "مرحله"


class MembershipPage(RoutablePageMixin, Page):
    """Benefits, fees, process, application forms, tracking and certificate check."""

    intro = models.TextField("خلاصه", blank=True)
    body = StreamField(BodyBlock(), verbose_name="مزایا و توضیحات", blank=True)

    producer_text = models.TextField("معرفی گروه: تولیدکننده", blank=True)
    institution_text = models.TextField("معرفی گروه: نهاد حمایتی", blank=True)
    network_text = models.TextField("معرفی گروه: شبکه تجارت عادلانه", blank=True)
    individual_text = models.TextField("معرفی گروه: فرد حامی", blank=True)
    fees_note = RichTextField("توضیح زیر جدول هزینه‌ها", blank=True)

    process_heading = models.CharField("عنوان بخش مراحل", max_length=200, blank=True)
    process_steps = StreamField([("step", ProcessStepBlock())], verbose_name="مراحل پذیرش", blank=True)
    conditions = RichTextField("شرایط عمومی پذیرش", blank=True)

    form_intro = RichTextField("متن بالای فرم درخواست", blank=True)
    commitment_text = RichTextField(
        "متن تعهدنامه اصول ده‌گانه", blank=True,
        help_text="متقاضی پیش از ارسال باید تیک پذیرش این متن را بزند",
    )
    inspection_text = models.TextField(
        "متن پذیرش بازرسی (فقط تولیدکنندگان)", blank=True,
    )
    payment_text = RichTextField("راهنمای پرداخت هزینه درخواست", blank=True)
    privacy_text = models.TextField("یادداشت محرمانگی مدارک", blank=True)
    success_text = RichTextField("پیام پس از ارسال درخواست", blank=True)
    closed_text = RichTextField("پیام وقتی پذیرش درخواست بسته است", blank=True)
    track_intro = RichTextField("متن صفحه پیگیری", blank=True)
    certificate_intro = RichTextField("متن صفحه استعلام گواهی", blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("body"),
        MultiFieldPanel(
            [FieldPanel("producer_text"), FieldPanel("institution_text"), FieldPanel("network_text"),
             FieldPanel("individual_text"), FieldPanel("fees_note")],
            heading="گروه‌های عضو و هزینه‌ها",
        ),
        MultiFieldPanel([FieldPanel("process_heading"), FieldPanel("process_steps"), FieldPanel("conditions")],
                        heading="فرایند پذیرش"),
        MultiFieldPanel(
            [FieldPanel("form_intro"), FieldPanel("payment_text"), FieldPanel("commitment_text"),
             FieldPanel("inspection_text"), FieldPanel("privacy_text"), FieldPanel("success_text"),
             FieldPanel("closed_text")],
            heading="فرم درخواست",
        ),
        MultiFieldPanel([FieldPanel("track_intro"), FieldPanel("certificate_intro")],
                        heading="پیگیری و استعلام گواهی"),
    ]
    search_fields = Page.search_fields + [index.SearchField("intro"), index.SearchField("body")]

    parent_page_types = ["home.HomePage"]
    max_count_per_parent = 1

    class Meta:
        verbose_name = "صفحه عضویت"

    def type_text(self, member_type):
        return getattr(self, f"{member_type}_text", "")

    def steps_with_values(self):
        from core.models import MembershipSettings

        ms = MembershipSettings.load()
        values = {
            "secretariat_days": ms.secretariat_review_days,
            "commission_days": ms.commission_review_days,
            "trial_months": ms.trial_period_months,
        }
        if not is_english():
            from .jalali import persian_digits

            values = {k: persian_digits(v) for k, v in values.items()}
        steps = []
        for block in self.process_steps:
            text = block.value["text"] or ""
            for key, value in values.items():
                text = text.replace("{" + key + "}", str(value))
            steps.append({"title": block.value["title"], "text": text})
        return steps

    # Routes. The views live in views.py so this file stays about data.

    @path("")
    def index_route(self, request):
        from . import views

        return views.membership_index(self, request)

    @path("apply/<str:member_type>/")
    def apply(self, request, member_type):
        from . import views

        return views.apply(self, request, member_type)

    @path("apply-done/")
    def apply_done(self, request):
        from . import views

        return views.apply_done(self, request)

    @path("track/")
    def track(self, request):
        from . import views

        return views.track(self, request)

    @path("certificate/")
    def certificate_check(self, request):
        from . import views

        return views.certificate_check(self, request)
