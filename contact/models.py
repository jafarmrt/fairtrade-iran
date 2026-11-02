"""
Contact page (questions editable in the admin, built on Wagtail's form
builder) and the confidential complaint form, whose submissions only the
Supervisory Commission can see.
"""

import os
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import models
from django.template.response import TemplateResponse
from django.urls import reverse
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from wagtail.fields import RichTextField
from wagtail.models import Page

from core.models import SiteSettings, is_english

from .storage import complaint_storage

COMMISSION_GROUP = "کمیسیون نظارتی"
HONEYPOT_FIELD = "website"


def site_root_url():
    return getattr(settings, "WAGTAILADMIN_BASE_URL", "").rstrip("/")


# ---------- contact page ----------


class ContactFormField(AbstractFormField):
    page = ParentalKey("ContactPage", on_delete=models.CASCADE, related_name="form_fields")


class ContactPage(AbstractEmailForm):
    intro = RichTextField("متن بالای فرم", blank=True)
    thank_you_text = RichTextField("متن پس از ارسال", blank=True)
    show_contact_details = models.BooleanField(
        "نمایش نشانی، تلفن و ایمیل", default=True,
        help_text="از «تنظیمات > تنظیمات سایت» خوانده می‌شود",
    )
    complaint_page = models.ForeignKey(
        "wagtailcore.Page", verbose_name="صفحه ثبت شکایت", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text="برای نمایش لینک «ثبت شکایت محرمانه» کنار فرم",
    )

    content_panels = AbstractEmailForm.content_panels + [
        FormSubmissionsPanel(),
        FieldPanel("intro"),
        InlinePanel("form_fields", label="پرسش‌های فرم"),
        FieldPanel("thank_you_text"),
        FieldPanel("show_contact_details"),
        FieldPanel("complaint_page"),
        MultiFieldPanel(
            [
                FieldRowPanel([FieldPanel("from_address"), FieldPanel("to_address")]),
                FieldPanel("subject"),
            ],
            heading="ایمیل اعلان",
            help_text="اگر «گیرنده» خالی باشد، پیام‌ها به ایمیل دبیرخانه در تنظیمات سایت فرستاده می‌شوند.",
        ),
    ]
    max_count_per_parent = 1
    subpage_types = []

    class Meta:
        verbose_name = "صفحه تماس"

    def serve(self, request, *args, **kwargs):
        # Bots fill every field, including the hidden one; pretend all went well.
        if request.method == "POST" and request.POST.get(HONEYPOT_FIELD):
            return self.render_landing_page(request)
        return super().serve(request, *args, **kwargs)

    def notification_addresses(self):
        raw = self.to_address or SiteSettings.load().notification_email
        return [a.strip() for a in (raw or "").split(",") if a.strip()]

    def process_form_submission(self, form):
        submission = self.get_submission_class().objects.create(form_data=form.cleaned_data, page=self)
        addresses = self.notification_addresses()
        if addresses:
            reply_to = [
                value for field in form for value in [form.cleaned_data.get(field.name)]
                if field.field.__class__.__name__ == "EmailField" and value
            ]
            EmailMessage(
                subject=self.subject or f"پیام تازه از فرم «{self.title}»",
                body=self.render_email(form),
                from_email=self.from_address or settings.DEFAULT_FROM_EMAIL,
                to=addresses,
                reply_to=reply_to[:1] or None,
            ).send(fail_silently=True)
        return submission


# ---------- confidential complaints ----------


def generate_tracking_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


def complaint_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()[:10]
    return f"{secrets.token_hex(16)}{ext}"


ALLOWED_ATTACHMENT_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".docx", ".zip"]
MAX_ATTACHMENT_MB = 10


def validate_attachment(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError("نوع فایل مجاز نیست. / File type not allowed.")
    if file.size > MAX_ATTACHMENT_MB * 1024 * 1024:
        raise ValidationError(f"حجم فایل بیش از {MAX_ATTACHMENT_MB} مگابایت است. / File is larger than {MAX_ATTACHMENT_MB} MB.")


class Complaint(models.Model):
    class Relation(models.TextChoices):
        MEMBER = "member", "عضو خانه"
        BUYER = "buyer", "خریدار"
        WORKER = "worker", "کارگر یا همکار یک عضو"
        PARTNER = "partner", "شریک تجاری یا نهاد"
        OTHER = "other", "سایر"

    class Category(models.TextChoices):
        PRINCIPLES = "principles", "نقض اصول تجارت عادلانه"
        WORK = "work", "شرایط کار و دستمزد"
        PRODUCT = "product", "کیفیت یا اصالت محصول"
        PAYMENT = "payment", "پرداخت یا معامله"
        GOVERNANCE = "governance", "عملکرد ارکان خانه"
        OTHER = "other", "سایر"

    class Status(models.TextChoices):
        RECEIVED = "received", "دریافت شده"
        REVIEWING = "reviewing", "در حال بررسی"
        NEEDS_INFO = "needs_info", "نیاز به اطلاعات بیشتر"
        RESOLVED = "resolved", "رسیدگی شد"
        DISMISSED = "dismissed", "رد شد"

    tracking_code = models.CharField("کد پیگیری", max_length=12, unique=True, default=generate_tracking_code, editable=False)
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)
    language = models.CharField("زبان فرم", max_length=5, default="fa", editable=False)

    name = models.CharField("نام شاکی", max_length=200, blank=True, help_text="خالی یعنی شکایت بی‌نام")
    email = models.EmailField("ایمیل", blank=True)
    phone = models.CharField("تلفن", max_length=40, blank=True)
    relation = models.CharField("نسبت شاکی", max_length=20, choices=Relation.choices, default=Relation.OTHER)
    subject_of_complaint = models.CharField("شکایت درباره", max_length=255,
                                            help_text="نام عضو، نهاد یا شخصی که شکایت درباره اوست")
    category = models.CharField("موضوع", max_length=20, choices=Category.choices, default=Category.OTHER)
    description = models.TextField("شرح شکایت")
    attachment = models.FileField("پیوست", upload_to=complaint_upload_to, storage=complaint_storage,
                                  blank=True, validators=[validate_attachment])

    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.RECEIVED)
    commission_notes = models.TextField("یادداشت‌های کمیسیون", blank=True,
                                        help_text="فقط اعضای کمیسیون این یادداشت را می‌بینند")

    class Meta:
        verbose_name = "شکایت"
        verbose_name_plural = "شکایات"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tracking_code} – {self.subject_of_complaint}"

    @property
    def is_anonymous(self):
        return not (self.name or self.email or self.phone)

    def attachment_url(self):
        if not self.attachment:
            return ""
        return reverse("complaint_file", args=[self.pk])


class ComplaintPage(Page):
    intro = RichTextField("متن بالای فرم", blank=True)
    privacy_note = RichTextField(
        "توضیح محرمانگی", blank=True,
        help_text="به شاکی توضیح دهید چه کسانی شکایت را می‌بینند و چگونه رسیدگی می‌شود",
    )
    thank_you_text = RichTextField("متن پس از ثبت", blank=True)
    extra_recipients = models.CharField(
        "ایمیل‌های دیگر برای اعلان", max_length=500, blank=True,
        help_text="به‌طور پیش‌فرض به ایمیل همه کاربران گروه «کمیسیون نظارتی» خبر داده می‌شود. "
                  "اعلان فقط کد پیگیری دارد، نه متن شکایت. چند نشانی را با ویرگول جدا کنید.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("privacy_note"),
        FieldPanel("thank_you_text"),
        FieldPanel("extra_recipients"),
    ]
    max_count_per_parent = 1
    subpage_types = []

    class Meta:
        verbose_name = "صفحه ثبت شکایت محرمانه"

    def get_form(self, data=None, files=None):
        from .forms import ComplaintForm

        return ComplaintForm(data, files)

    def serve(self, request, *args, **kwargs):
        if request.method == "POST":
            if request.POST.get(HONEYPOT_FIELD):
                return self.render_done(request, None)
            form = self.get_form(request.POST, request.FILES)
            if form.is_valid():
                complaint = form.save(commit=False)
                complaint.language = "en" if is_english() else "fa"
                complaint.save()
                self.notify_commission(complaint)
                return self.render_done(request, complaint)
        else:
            form = self.get_form()
        context = self.get_context(request, *args, **kwargs)
        context["form"] = form
        response = TemplateResponse(request, self.get_template(request, *args, **kwargs), context)
        response["Cache-Control"] = "no-store"
        return response

    def render_done(self, request, complaint):
        context = self.get_context(request)
        context["complaint"] = complaint
        response = TemplateResponse(request, "contact/complaint_page_landing.html", context)
        response["Cache-Control"] = "no-store"
        return response

    def recipients(self):
        emails = set(
            get_user_model().objects.filter(groups__name=COMMISSION_GROUP, is_active=True)
            .exclude(email="").values_list("email", flat=True)
        )
        emails.update(a.strip() for a in self.extra_recipients.split(",") if a.strip())
        return sorted(emails)

    def notify_commission(self, complaint):
        to = self.recipients()
        if not to:
            return
        link = site_root_url() + reverse("complaints:edit", args=[complaint.pk])
        EmailMessage(
            subject=f"شکایت تازه ثبت شد: {complaint.tracking_code}",
            body=(
                "یک شکایت محرمانه تازه در سایت ثبت شد.\n"
                f"کد پیگیری: {complaint.tracking_code}\n\n"
                "برای حفظ محرمانگی، متن شکایت در این ایمیل نیامده است. "
                f"برای خواندن آن وارد پنل مدیریت شوید:\n{link}\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to,
        ).send(fail_silently=True)
