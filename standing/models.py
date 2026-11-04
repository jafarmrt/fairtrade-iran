"""
Annual membership fees and the standing of accepted members, following
sections 1.7 (suspension), 1.8 (cancellation), 7 (disciplinary steps) and
8.2 (appeals) of the governance document (سند ارکان، نسخه ۲).

    dues issued -> reminder -> due date passes -> written warning ->
    3 months after the warning, still unpaid -> suspended (max. 6 months)
    -> paid: suspension lifted / still suspended: lift or cancel.

Amounts, dates and texts come from core.MembershipSettings.
"""

import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from archive.storage import PrivateStorage
from core.models import is_english


class DuesStorage(PrivateStorage):
    """PRIVATE_MEDIA_ROOT/dues/: payment receipts, served only by a staff-checked view."""

    def __init__(self):
        super().__init__("dues")

    def url(self, name):
        raise ValueError("Private files have no public URL.")


def dues_storage():
    return DuesStorage()


def receipt_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()[:10]
    return f"{instance.dues.member_id}/{instance.dues.year}/{uuid.uuid4().hex}{ext}"


def _label(choices_en, value, display):
    return choices_en.get(value, display) if is_english() else display


class Dues(models.Model):
    """One member's fee for one membership year."""

    class Status(models.TextChoices):
        UNPAID = "unpaid", "پرداخت نشده"
        PENDING = "pending", "رسید در انتظار بررسی"
        PAID = "paid", "پرداخت شده"
        WAIVED = "waived", "بخشوده"

    STATUS_EN = {
        Status.UNPAID: "Not paid",
        Status.PENDING: "Receipt being checked",
        Status.PAID: "Paid",
        Status.WAIVED: "Waived",
    }
    OPEN = (Status.UNPAID, Status.PENDING)

    member = models.ForeignKey("members.Member", verbose_name="عضو", on_delete=models.CASCADE, related_name="dues")
    year = models.PositiveSmallIntegerField("سال عضویت (شمسی)")
    period_start = models.DateField("آغاز سال عضویت")
    due_date = models.DateField("مهلت پرداخت", db_index=True)
    amount = models.PositiveBigIntegerField("مبلغ (ریال)")
    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.UNPAID, db_index=True)

    reminded_on = models.DateField("یادآوری فرستاده شد", null=True, blank=True)
    warned_on = models.DateField("اخطار کتبی فرستاده شد", null=True, blank=True)
    suspension_flagged_on = models.DateField("رسیدن به زمان تعلیق", null=True, blank=True)

    paid_on = models.DateField("تاریخ تأیید پرداخت", null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="تأیید یا بخشودگی توسط", null=True,
                                  blank=True, on_delete=models.SET_NULL, related_name="+")
    internal_note = models.TextField("یادداشت داخلی", blank=True)
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)

    class Meta:
        verbose_name = "حق عضویت سالانه"
        verbose_name_plural = "حق عضویت‌های سالانه"
        ordering = ["-year", "member__name"]
        constraints = [models.UniqueConstraint(fields=["member", "year"], name="dues_one_per_member_year")]

    def __str__(self):
        return f"{self.member} | {self.year}"

    @property
    def status_display(self):
        return _label(self.STATUS_EN, self.status, self.get_status_display())

    @property
    def is_open(self):
        return self.status in self.OPEN

    @property
    def is_overdue(self):
        return self.is_open and self.due_date < timezone.localdate()

    @property
    def can_pay(self):
        """The member can send a receipt (also again after a rejected one)."""
        return self.status == self.Status.UNPAID

    def suspension_date(self, ms):
        """When the member may be suspended for this debt (warning + N months), or None."""
        if not self.warned_on:
            return None
        from membership.models import add_months

        return add_months(self.warned_on, ms.dues_suspend_months)


class DuesPayment(models.Model):
    """A receipt the member sent from the panel, or a payment staff recorded."""

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار بررسی"
        CONFIRMED = "confirmed", "تأیید شد"
        REJECTED = "rejected", "پذیرفته نشد"

    STATUS_EN = {Status.PENDING: "Being checked", Status.CONFIRMED: "Confirmed", Status.REJECTED: "Not accepted"}

    dues = models.ForeignKey(Dues, verbose_name="حق عضویت", on_delete=models.CASCADE, related_name="payments")
    amount = models.PositiveBigIntegerField("مبلغ واریزی (ریال)")
    reference = models.CharField("شماره پیگیری یا شماره سند", max_length=100, blank=True)
    paid_on_text = models.CharField("تاریخ واریز", max_length=40, blank=True)
    receipt = models.FileField("تصویر رسید", storage=dues_storage, upload_to=receipt_upload_to, max_length=255,
                               blank=True)
    original_name = models.CharField("نام اصلی فایل", max_length=255, blank=True)
    payer_note = models.TextField("توضیح پرداخت‌کننده", blank=True)
    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.PENDING)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="فرستنده", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    submitted_at = models.DateTimeField("تاریخ ارسال", default=timezone.now)
    recorded_by_staff = models.BooleanField("ثبت دستی دبیرخانه", default=False)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="بررسی‌کننده", null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField("تاریخ بررسی", null=True, blank=True)
    staff_message = models.TextField("پیام دبیرخانه به عضو", blank=True)

    class Meta:
        verbose_name = "پرداخت حق عضویت"
        verbose_name_plural = "پرداخت‌های حق عضویت"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.dues} | {self.amount}"

    @property
    def status_display(self):
        return _label(self.STATUS_EN, self.status, self.get_status_display())


class Decision(models.Model):
    """
    A step in a member's standing: written notice, written warning,
    suspension, lifting it, cancellation or reinstatement after an appeal.
    """

    class Kind(models.TextChoices):
        NOTICE = "notice", "تذکر کتبی"
        WARNING = "warning", "اخطار کتبی"
        SUSPEND = "suspend", "تعلیق عضویت"
        LIFT = "lift", "رفع تعلیق"
        CANCEL = "cancel", "لغو عضویت"
        REINSTATE = "reinstate", "بازگشت عضویت (نقض رأی در اعتراض)"

    KIND_EN = {
        Kind.NOTICE: "Written notice",
        Kind.WARNING: "Written warning",
        Kind.SUSPEND: "Membership suspended",
        Kind.LIFT: "Suspension lifted",
        Kind.CANCEL: "Membership cancelled",
        Kind.REINSTATE: "Membership reinstated after appeal",
    }

    class Reason(models.TextChoices):
        DUES = "dues", "عدم پرداخت حق عضویت"
        MINOR = "minor", "تخلف جزئی"
        AUDIT = "audit", "عدم رفع مغایرت‌های ممیزی در مهلت تعیین‌شده"
        INSPECTION = "inspection", "خودداری از پذیرش بازرسی"
        COMPLAINT = "complaint", "طرح شکایت جدی (تا پایان رسیدگی)"
        RESIGNATION = "resignation", "استعفای کتبی عضو"
        SERIOUS = "serious", "تخلف جدی (کار کودک، کار اجباری، جعل مدارک، سوءاستفاده از نشان)"
        LONG_SUSPENSION = "long_suspension", "ادامه وضعیت تعلیق بیش از مدت مجاز"
        DISSOLUTION = "dissolution", "انحلال شخص حقوقی یا فوت شخص حقیقی"
        PAID = "paid", "پرداخت بدهی حق عضویت"
        RESOLVED = "resolved", "رفع موضوع تعلیق"
        APPEAL = "appeal", "نقض رأی در رسیدگی به اعتراض"
        OTHER = "other", "سایر"

    REASON_EN = {
        Reason.DUES: "Membership fee not paid",
        Reason.MINOR: "Minor breach",
        Reason.AUDIT: "Audit findings not corrected in time",
        Reason.INSPECTION: "Refused an inspection",
        Reason.COMPLAINT: "Serious complaint under review",
        Reason.RESIGNATION: "Written resignation",
        Reason.SERIOUS: "Serious breach",
        Reason.LONG_SUSPENSION: "Suspended longer than allowed",
        Reason.DISSOLUTION: "Dissolution or death",
        Reason.PAID: "Membership fee paid",
        Reason.RESOLVED: "Cause of suspension resolved",
        Reason.APPEAL: "Decision overturned on appeal",
        Reason.OTHER: "Other",
    }

    class Body(models.TextChoices):
        SECRETARIAT = "secretariat", "دبیرخانه"
        COMMISSION = "commission", "کمیسیون نظارتی"
        SYSTEM = "system", "خودکار (طبق تنظیمات)"

    member = models.ForeignKey("members.Member", verbose_name="عضو", on_delete=models.CASCADE,
                               related_name="decisions")
    kind = models.CharField("نوع", max_length=20, choices=Kind.choices)
    reason = models.CharField("دلیل", max_length=30, choices=Reason.choices)
    decided_by = models.CharField("مرجع", max_length=20, choices=Body.choices)
    decision_reference = models.CharField("شماره/تاریخ صورتجلسه", max_length=200, blank=True)
    decided_on = models.DateField("تاریخ", default=timezone.localdate)
    message = models.TextField("پیام به عضو", blank=True)
    internal_note = models.TextField("یادداشت داخلی", blank=True)
    ends_on = models.DateField("پایان تعلیق", null=True, blank=True)
    reapply_after = models.DateField("امکان درخواست دوباره از", null=True, blank=True)
    appeal_until = models.DateField("مهلت اعتراض تا", null=True, blank=True)
    dues = models.ForeignKey(Dues, verbose_name="حق عضویت مربوط", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="decisions")
    from_status = models.CharField("وضعیت قبلی", max_length=20, blank=True)
    to_status = models.CharField("وضعیت جدید", max_length=20, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="ثبت‌کننده", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)

    class Meta:
        verbose_name = "رأی و اقدام انضباطی"
        verbose_name_plural = "آرا و اقدامات انضباطی"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member} | {self.get_kind_display()}"

    @property
    def kind_display(self):
        return _label(self.KIND_EN, self.kind, self.get_kind_display())

    @property
    def reason_display(self):
        return _label(self.REASON_EN, self.reason, self.get_reason_display())

    APPEALABLE_KINDS = {Kind.WARNING, Kind.SUSPEND, Kind.CANCEL}  # governance doc 8.2

    @property
    def can_appeal(self):
        """Whether the member can still appeal this decision from the panel (appeals app)."""
        return (self.kind in self.APPEALABLE_KINDS and self.appeal_until is not None
                and self.appeal_until >= timezone.localdate() and not self.appeals.exists())
