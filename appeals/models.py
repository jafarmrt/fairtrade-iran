"""
Members' appeals against decisions about their membership, following
section 8.2 of the governance document (سند ارکان، نسخه ۲):

    a member may appeal in writing to the Secretary of the General Assembly
    within 30 days of being notified of a rejection, written warning,
    suspension or revocation; the secretary upholds or overturns the
    decision within 30 days (an overturn must give reasons), may hold a
    hearing, and the ruling is final. An appeal does not stop a suspension.

Both deadlines and every text members or staff read are edited in the admin
panel (Settings → اعتراض‌ها).
"""

import datetime
import os
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList, TabbedInterface
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField

from core.models import BilingualMixin, is_english

from .storage import appeal_storage

SECRETARY_GROUP = "دبیر مجمع"  # created by seed_content (home/management/commands/seed_data.py)

ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".docx", ".zip"]
MAX_ATTACHMENT_MB = 10


def validate_attachment(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("نوع فایل مجاز نیست. / File type not allowed.")
    if file.size > MAX_ATTACHMENT_MB * 1024 * 1024:
        raise ValidationError(f"حجم فایل بیش از {MAX_ATTACHMENT_MB} مگابایت است. / File is larger than {MAX_ATTACHMENT_MB} MB.")


def attachment_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()[:10]
    return f"{secrets.token_hex(16)}{ext}"


def new_tracking_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = "AP-" + "".join(secrets.choice(alphabet) for _ in range(7))
        if not Appeal.objects.filter(tracking_code=code).exists():
            return code


@register_setting(icon="resubmit")
class AppealSettings(BaseGenericSetting):
    # The appeal window itself is MembershipSettings.appeal_days (تنظیمات عضویت), shared with the
    # appeal deadline written on suspension and cancellation notices.
    enabled = models.BooleanField("ثبت اعتراض از پنل اعضا فعال است", default=True)
    decision_days = models.PositiveSmallIntegerField(
        "مهلت رأی دبیر مجمع پس از دریافت اعتراض (روز)", default=30, help_text="سند ارکان، بند ۸-۲: ۳۰ روز",
    )
    extra_recipients = models.CharField(
        "ایمیل‌های دیگر برای اعلان اعتراض تازه", max_length=500, blank=True,
        help_text="به‌طور پیش‌فرض به همه کاربران گروه «دبیر مجمع» (دبیر و جانشین او) خبر داده می‌شود. اگر این گروه "
                  "کاربری نداشته باشد، به ایمیل اطلاع‌رسانی تنظیمات سایت. چند نشانی را با ویرگول جدا کنید.",
    )

    intro = RichTextField(
        "توضیح بالای فرم اعتراض (فارسی)", blank=True,
        default="<p>طبق بند ۸-۲ سند ارکان، می‌توانید ظرف ۳۰ روز از ابلاغ رأی رد عضویت، اخطار، تعلیق یا لغو عضویت، "
                "اعتراض کتبی خود را به دبیر مجمع عمومی بدهید. دبیر مجمع پرونده را از کمیسیون یا دبیرخانه می‌گیرد، "
                "در صورت نیاز جلسه رسیدگی با حضور شما برگزار می‌کند و ظرف ۳۰ روز رأی را تأیید یا نقض می‌کند. "
                "رأی دبیر مجمع قطعی است.</p><p>اعتراض، اجرای تعلیق را متوقف نمی‌کند.</p>",
    )
    intro_en = RichTextField(
        "توضیح بالای فرم اعتراض (انگلیسی)", blank=True,
        default="<p>Under clause 8.2 of the governance document, you may appeal in writing to the Secretary of the "
                "General Assembly within 30 days of being notified of a membership rejection, written warning, "
                "suspension or revocation. The secretary obtains the file from the commission or the secretariat, "
                "may hold a hearing with you, and upholds or overturns the decision within 30 days. The "
                "secretary's ruling is final.</p><p>An appeal does not put a suspension on hold.</p>",
    )
    complaint_intro = RichTextField(
        "توضیح بالای فرم شکایت در پنل (فارسی)", blank=True,
        default="<p>شکایت شما مستقیم به کمیسیون نظارتی می‌رسد و فقط اعضای کمیسیون آن را می‌بینند. وضعیت رسیدگی و "
                "پاسخ کمیسیون را در همین صفحه می‌بینید.</p>",
    )
    complaint_intro_en = RichTextField(
        "توضیح بالای فرم شکایت در پنل (انگلیسی)", blank=True,
        default="<p>Your complaint goes straight to the Supervisory Commission and only its members can read it. "
                "You can follow its progress and the commission's answer on this page.</p>",
    )

    received_subject = models.CharField("موضوع ایمیل دریافت اعتراض (فارسی)", max_length=200,
                                        default="اعتراض شما دریافت شد ({code})")
    received_body = models.TextField(
        "متن ایمیل دریافت اعتراض (فارسی)",
        default="{name} گرامی،\n\nاعتراض شما به «{decision}» با کد پیگیری {code} ثبت شد و به دبیر مجمع عمومی رسید. "
                "رأی دبیر مجمع حداکثر تا {decide_by} اعلام می‌شود.\n\nپیگیری در پنل اعضا:\n{panel_url}\n\n{site_name}",
        help_text="می‌توانید از این‌ها استفاده کنید: {name} {code} {decision} {status} {decide_by} {hearing_date} {ruling} {panel_url} {site_name}",
    )
    received_subject_en = models.CharField("موضوع ایمیل دریافت اعتراض (انگلیسی)", max_length=200, blank=True,
                                           default="We have received your appeal ({code})")
    received_body_en = models.TextField(
        "متن ایمیل دریافت اعتراض (انگلیسی)", blank=True,
        default="Dear {name},\n\nYour appeal against \"{decision}\" has been registered with the code {code} and "
                "passed to the Secretary of the General Assembly. You will have a ruling by {decide_by}.\n\n"
                "Follow it in the member panel:\n{panel_url}\n\n{site_name}",
    )
    update_subject = models.CharField("موضوع ایمیل تغییر وضعیت اعتراض (فارسی)", max_length=200,
                                      default="وضعیت اعتراض {code}: {status}")
    update_body = models.TextField(
        "متن ایمیل تغییر وضعیت اعتراض (فارسی)",
        default="{name} گرامی،\n\nوضعیت اعتراض شما ({code}) به «{status}» تغییر کرد.\n\n{ruling}\n\n"
                "جزئیات در پنل اعضا:\n{panel_url}\n\n{site_name}",
        help_text="وقتی دبیر مجمع وضعیت را تغییر می‌دهد فرستاده می‌شود. همان متغیرهای بالا.",
    )
    update_subject_en = models.CharField("موضوع ایمیل تغییر وضعیت اعتراض (انگلیسی)", max_length=200, blank=True,
                                         default="Your appeal {code}: {status}")
    update_body_en = models.TextField(
        "متن ایمیل تغییر وضعیت اعتراض (انگلیسی)", blank=True,
        default="Dear {name},\n\nThe status of your appeal ({code}) is now \"{status}\".\n\n{ruling}\n\n"
                "Details in the member panel:\n{panel_url}\n\n{site_name}",
    )

    edit_handler = TabbedInterface([
        ObjectList([
            FieldPanel("enabled"), FieldPanel("decision_days"),
            FieldPanel("extra_recipients"),
        ], heading="مهلت‌ها و اعلان"),
        ObjectList([
            MultiFieldPanel([FieldPanel("intro"), FieldPanel("intro_en")], heading="فرم اعتراض"),
            MultiFieldPanel([FieldPanel("complaint_intro"), FieldPanel("complaint_intro_en")], heading="فرم شکایت"),
        ], heading="متن‌های پنل"),
        ObjectList([
            MultiFieldPanel([FieldPanel("received_subject"), FieldPanel("received_body"),
                             FieldPanel("received_subject_en"), FieldPanel("received_body_en")],
                            heading="به عضو: اعتراض دریافت شد"),
            MultiFieldPanel([FieldPanel("update_subject"), FieldPanel("update_body"),
                             FieldPanel("update_subject_en"), FieldPanel("update_body_en")],
                            heading="به عضو: تغییر وضعیت یا رأی"),
        ], heading="ایمیل‌ها"),
    ])

    class Meta:
        verbose_name = "اعتراض‌ها و شکایت‌های اعضا"

    def tr(self, field):
        return BilingualMixin.tr(self, field)


class Appeal(models.Model):
    class Decision(models.TextChoices):
        REJECTION = "rejection", "رد عضویت"
        WARNING = "warning", "اخطار کتبی"
        SUSPENSION = "suspension", "تعلیق عضویت"
        REVOCATION = "revocation", "لغو عضویت"

    class Body(models.TextChoices):
        COMMISSION = "commission", "کمیسیون نظارتی"
        SECRETARIAT = "secretariat", "دبیرخانه"
        OTHER = "other", "نمی‌دانم / سایر"

    class Status(models.TextChoices):
        RECEIVED = "received", "دریافت شد"
        REVIEWING = "reviewing", "در حال بررسی دبیر مجمع"
        HEARING = "hearing", "جلسه رسیدگی تعیین شد"
        UPHELD = "upheld", "رأی تأیید شد"
        OVERTURNED = "overturned", "رأی نقض شد"
        DISMISSED = "dismissed", "رد شکلی (خارج از مهلت یا ناقص)"

    DECISION_EN = {"rejection": "Membership rejection", "warning": "Written warning",
                   "suspension": "Suspension", "revocation": "Revocation of membership"}
    BODY_EN = {"commission": "Supervisory Commission", "secretariat": "Secretariat", "other": "Not sure / other"}
    STATUS_EN = {"received": "Received", "reviewing": "Being reviewed by the Assembly Secretary",
                 "hearing": "Hearing scheduled", "upheld": "Decision upheld", "overturned": "Decision overturned",
                 "dismissed": "Not admissible (late or incomplete)"}
    FINAL = {Status.UPHELD, Status.OVERTURNED, Status.DISMISSED}

    tracking_code = models.CharField("کد پیگیری", max_length=12, unique=True, editable=False)
    member = models.ForeignKey("members.Member", verbose_name="عضو", null=True, on_delete=models.SET_NULL,
                               related_name="appeals")
    application = models.ForeignKey(
        "membership.MembershipApplication", verbose_name="پرونده عضویت", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="appeals",
        help_text="برای متقاضیانی که پیش از دوره آزمایشی رد شده‌اند و از صفحه پیگیری درخواست اعتراض کرده‌اند",
    )
    standing_decision = models.ForeignKey(
        "standing.Decision", verbose_name="رأی ثبت‌شده در سایت", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="appeals",
        help_text="اگر رأی نقض شود، دبیرخانه «بازگشت عضویت» یا «رفع تعلیق» را در وضعیت عضو ثبت می‌کند",
    )
    member_name = models.CharField("نام عضو هنگام ثبت", max_length=200, editable=False)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="ثبت‌کننده", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    email = models.EmailField("ایمیل برای پاسخ", blank=True)
    phone = models.CharField("تلفن", max_length=40, blank=True)
    language = models.CharField("زبان", max_length=5, default="fa", editable=False)
    submitted_at = models.DateTimeField("تاریخ ثبت", default=timezone.now, editable=False)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)

    decision = models.CharField("اعتراض به", max_length=20, choices=Decision.choices)
    decision_body = models.CharField("مرجع صادرکننده رأی", max_length=20, choices=Body.choices, default=Body.OTHER)
    decision_date = models.DateField("تاریخ ابلاغ رأی")
    decision_reference = models.CharField("شماره یا عنوان نامه رأی", max_length=200, blank=True)
    grounds = models.TextField("دلایل اعتراض")
    attachment = models.FileField("پیوست", upload_to=attachment_upload_to, storage=appeal_storage, blank=True,
                                  max_length=255, validators=[validate_attachment])

    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    decide_by = models.DateField("مهلت صدور رأی", null=True, blank=True)
    handled_by_deputy = models.BooleanField(
        "رسیدگی با جانشین دبیر", default=False, help_text="در غیبت یا تعارض منافع دبیر مجمع (بند ۸-۲)",
    )
    hearing_date = models.DateField("تاریخ جلسه رسیدگی", null=True, blank=True,
                                    help_text="اگر جلسه لازم است؛ با حضور معترض و نماینده کمیسیون یا دبیرخانه")
    ruling = models.TextField(
        "رأی و دلایل (به عضو نمایش داده می‌شود)", blank=True,
        help_text="برای تأیید، نقض یا رد شکلی لازم است. نقض رأی باید مستدل باشد.",
    )
    ruled_on = models.DateField("تاریخ رأی", null=True, blank=True)
    secretary_notes = models.TextField("یادداشت داخلی دبیر مجمع", blank=True, help_text="عضو این یادداشت را نمی‌بیند")

    class Meta:
        verbose_name = "اعتراض"
        verbose_name_plural = "اعتراض‌ها"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.tracking_code} – {self.member_name}"

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._loaded_status = instance.status
        return instance

    def clean(self):
        if self.status in self.FINAL and not self.ruling.strip():
            raise ValidationError({"ruling": "برای این وضعیت، متن رأی و دلایل آن را بنویسید (سند ارکان، بند ۸-۲)."})

    def save(self, *args, **kwargs):
        if not self.tracking_code:
            self.tracking_code = new_tracking_code()
        if self.decide_by is None:
            days = AppealSettings.load().decision_days
            self.decide_by = timezone.localtime(self.submitted_at).date() + datetime.timedelta(days=days)
        if self.status in self.FINAL and self.ruled_on is None:
            self.ruled_on = timezone.localdate()
        elif self.status not in self.FINAL:
            self.ruled_on = None
        super().save(*args, **kwargs)

    @property
    def status_changed(self):
        return getattr(self, "_loaded_status", self.status) != self.status

    # ---- display ----

    @property
    def decision_display(self):
        return self.DECISION_EN.get(self.decision, self.decision) if is_english() else self.get_decision_display()

    @property
    def body_display(self):
        return self.BODY_EN.get(self.decision_body, "") if is_english() else self.get_decision_body_display()

    @property
    def status_display(self):
        return self.STATUS_EN.get(self.status, self.status) if is_english() else self.get_status_display()

    @property
    def is_final(self):
        return self.status in self.FINAL

    @property
    def is_overdue(self):
        return not self.is_final and bool(self.decide_by and self.decide_by < timezone.localdate())

    def attachment_url(self):
        return reverse("appeal_file", args=[self.pk]) if self.attachment else ""
