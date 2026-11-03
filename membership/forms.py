import os

from django import forms
from django.core.exceptions import ValidationError

from core.models import MembershipSettings

from .models import ApplicationQuestion, MemberType


def t(fa, en, is_en):
    return en if is_en else fa


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(d, initial) for d in data if d]
        return [single(data, initial)] if data else []


def check_upload(upload, ms, is_en):
    if not upload:
        return
    ext = os.path.splitext(upload.name)[1].lstrip(".").lower()
    allowed = ms.upload_extensions
    if allowed and ext not in allowed:
        raise ValidationError(t(
            f"این نوع فایل پذیرفته نیست. پسوندهای مجاز: {'، '.join(allowed)}",
            f"This file type is not accepted. Allowed: {', '.join(allowed)}", is_en))
    if upload.size > ms.max_upload_mb * 1024 * 1024:
        raise ValidationError(t(
            f"حجم هر فایل باید کمتر از {ms.max_upload_mb} مگابایت باشد.",
            f"Each file must be smaller than {ms.max_upload_mb} MB.", is_en))


NAME_LABELS = {
    MemberType.PRODUCER: ("نام گروه، کارگاه یا کسب‌وکار", "Name of the group, workshop or business"),
    MemberType.INSTITUTION: ("نام نهاد", "Name of the organisation"),
    MemberType.NETWORK: ("نام شبکه", "Name of the network"),
    MemberType.INDIVIDUAL: ("نام و نام خانوادگی", "Full name"),
}


class ApplicationForm(forms.Form):
    """The application form. Questions per member type come from ApplicationQuestion snippets."""

    def __init__(self, *args, member_type, is_en=False, page=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.member_type = member_type
        self.is_en = is_en
        self.ms = MembershipSettings.load()
        self.questions = list(ApplicationQuestion.for_type(member_type))
        en = is_en

        name_fa, name_en = NAME_LABELS[member_type]
        f = self.fields
        f["name"] = forms.CharField(label=t(name_fa, name_en, en), max_length=200)
        # On the English form "name" is the English name and "name_en" asks for the Persian one.
        f["name_en"] = forms.CharField(
            label=t("نام به انگلیسی (اختیاری)", "Name in Persian, if any (optional)", en),
            max_length=200, required=False)
        if member_type != MemberType.INDIVIDUAL:
            f["contact_person"] = forms.CharField(label=t("نام و سمت رابط", "Contact person and role", en),
                                                  max_length=150)
        f["email"] = forms.EmailField(label=t("ایمیل", "E-mail", en))
        f["phone"] = forms.CharField(label=t("تلفن همراه", "Mobile phone", en), max_length=40)
        f["city"] = forms.CharField(label=t("استان و شهر", "Province and city", en), max_length=150)
        f["address"] = forms.CharField(label=t("نشانی", "Address", en), required=False,
                                       widget=forms.Textarea(attrs={"rows": 2}))
        f["website"] = forms.CharField(
            label=t("وب‌سایت یا صفحه اینستاگرام", "Website or Instagram page", en), max_length=300, required=False)

        self.question_fields = []
        for q in self.questions:
            name = f"q_{q.pk}"
            f[name] = self.question_field(q)
            self.question_fields.append(name)

        f["referred_by"] = forms.CharField(
            label=t("معرف (اختیاری)", "Referred by (optional)", en), max_length=200, required=False,
            help_text=t("اگر کارگروه توسعه بازار یا یکی از اعضا شما را معرفی کرده است",
                        "If the market development working group or a member referred you", en))

        self.fee = self.ms.application_fee_for(member_type)
        self.pay_online = False
        if self.fee:
            from payments.services import online_enabled

            self.pay_online = online_enabled("application_fee")
            f["receipt"] = forms.FileField(
                label=t("تصویر رسید پرداخت هزینه درخواست", "Receipt of the application fee payment", en),
                required=not self.pay_online,
                help_text=t("اگر می‌خواهید پس از ثبت درخواست آنلاین بپردازید، خالی بگذارید.",
                            "Leave empty if you prefer to pay online right after submitting.", en)
                if self.pay_online else "")
            f["payment_reference"] = forms.CharField(
                label=t("شماره پیگیری پرداخت", "Payment reference number", en), max_length=100, required=False)

        f["documents"] = MultipleFileField(
            label=t("مدارک دیگر (اختیاری)", "Other documents (optional)", en), required=False,
            help_text=t("می‌توانید چند فایل را با هم انتخاب کنید", "You can select several files at once", en))

        f["agreed_principles"] = forms.BooleanField(
            label=t("متن تعهدنامه رعایت اصول ده‌گانه تجارت عادلانه را خواندم و می‌پذیرم.",
                    "I have read and accept the commitment to the ten principles of fair trade.", en))
        if member_type == MemberType.PRODUCER:
            f["agreed_inspections"] = forms.BooleanField(
                label=(page.inspection_text if page and page.inspection_text else
                       t("بازرسی‌های دوره‌ای و سرزده خانه را می‌پذیرم.",
                         "I accept periodic and unannounced inspections by the House.", en)))
        # Honeypot: real people leave it empty.
        f["nickname"] = forms.CharField(required=False, label="Leave empty",
                                        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def question_field(self, q):
        label = q.tr("label")
        help_text = q.tr("help_text")
        kwargs = {"label": label, "help_text": help_text, "required": q.required}
        FT = ApplicationQuestion.FieldType
        if q.field_type == FT.TEXTAREA:
            return forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), max_length=5000, **kwargs)
        if q.field_type == FT.NUMBER:
            return forms.DecimalField(**kwargs)
        if q.field_type == FT.EMAIL:
            return forms.EmailField(**kwargs)
        if q.field_type == FT.URL:
            return forms.CharField(max_length=500, **kwargs)
        if q.field_type == FT.DATE:
            return forms.CharField(max_length=40, **kwargs)
        if q.field_type == FT.SELECT:
            choices = [("", "---------")] + q.choice_list()
            return forms.ChoiceField(choices=choices, **kwargs)
        if q.field_type == FT.CHECKBOX:
            return forms.BooleanField(**kwargs)
        if q.field_type == FT.FILE:
            return forms.FileField(**kwargs)
        return forms.CharField(max_length=500, **kwargs)

    # ---- validation ----

    def clean_nickname(self):
        if self.cleaned_data.get("nickname"):
            raise ValidationError("spam")
        return ""

    def clean(self):
        cleaned = super().clean()
        for name, field in self.fields.items():
            value = cleaned.get(name)
            if isinstance(field, MultipleFileField):
                for upload in value or []:
                    try:
                        check_upload(upload, self.ms, self.is_en)
                    except ValidationError as e:
                        self.add_error(name, e)
                        break
            elif isinstance(field, forms.FileField) and value:
                try:
                    check_upload(value, self.ms, self.is_en)
                except ValidationError as e:
                    self.add_error(name, e)
        return cleaned

    # ---- results ----

    def answers(self):
        """Answers to the editable questions, with the question text kept for the record."""
        result = []
        for q in self.questions:
            value = self.cleaned_data.get(f"q_{q.pk}")
            if q.field_type == ApplicationQuestion.FieldType.FILE:
                value = getattr(value, "name", "") if value else ""
            elif q.field_type == ApplicationQuestion.FieldType.CHECKBOX:
                value = "بله" if value else "خیر"
            elif value is None:
                value = ""
            result.append({"question": q.pk, "label": q.label, "type": q.field_type, "value": str(value)})
        return result

    def question_files(self):
        for q in self.questions:
            if q.field_type == ApplicationQuestion.FieldType.FILE:
                upload = self.cleaned_data.get(f"q_{q.pk}")
                if upload:
                    yield q, upload


class TrackForm(forms.Form):
    def __init__(self, *args, is_en=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"] = forms.CharField(label=t("کد پیگیری", "Tracking code", is_en), max_length=20)
        self.fields["email"] = forms.EmailField(label=t("ایمیلی که در فرم نوشتید", "The e-mail you used in the form", is_en))

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class ResubmitForm(forms.Form):
    def __init__(self, *args, is_en=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_en = is_en
        self.ms = MembershipSettings.load()
        self.fields["message"] = forms.CharField(
            label=t("توضیح شما", "Your reply", is_en), widget=forms.Textarea(attrs={"rows": 4}), required=False,
            max_length=5000)
        self.fields["documents"] = MultipleFileField(
            label=t("مدارک", "Documents", is_en), required=False,
            help_text=t("می‌توانید چند فایل را با هم انتخاب کنید", "You can select several files at once", is_en))

    def clean(self):
        cleaned = super().clean()
        for upload in cleaned.get("documents") or []:
            try:
                check_upload(upload, self.ms, self.is_en)
            except ValidationError as e:
                self.add_error("documents", e)
                break
        if not cleaned.get("message") and not cleaned.get("documents"):
            raise ValidationError(t("یک توضیح بنویسید یا فایلی بفرستید.", "Write a reply or attach a file.", self.is_en))
        return cleaned


class StaffActionForm(forms.Form):
    action = forms.CharField(widget=forms.HiddenInput)
    message = forms.CharField(
        label="پیام به متقاضی", required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="در ایمیل متقاضی و صفحه پیگیری او نمایش داده می‌شود")
    internal_note = forms.CharField(
        label="یادداشت داخلی", required=False, widget=forms.Textarea(attrs={"rows": 2}),
        help_text="فقط دبیرخانه و کمیسیون می‌بینند")
    decision_reference = forms.CharField(label="شماره یا تاریخ صورتجلسه کمیسیون", required=False, max_length=200)
    field_visit_date = forms.DateField(label="تاریخ بازدید (میلادی، مثلاً 2026-11-02)", required=False,
                                       widget=forms.DateInput(attrs={"type": "date"}))
    field_visit_report = forms.CharField(label="خلاصه گزارش بازدید", required=False,
                                         widget=forms.Textarea(attrs={"rows": 3}))
