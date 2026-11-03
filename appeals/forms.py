import datetime

from django import forms
from django.utils import timezone

from contact.models import ALLOWED_ATTACHMENT_EXTENSIONS, MAX_ATTACHMENT_MB, Complaint
from contact.forms import CHOICES_EN as COMPLAINT_CHOICES_EN
from core.models import is_english
from membership.jalali import format_jalali, parse_date

from .models import ALLOWED_EXTENSIONS, Appeal


def tr(fa, en):
    return en if is_english() else fa


class DateInputField(forms.CharField):
    """A date typed in the Jalali calendar (Persian) or Gregorian (English)."""

    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return None
        day = parse_date(value)
        if day is None:
            raise forms.ValidationError(tr("تاریخ را به شکل ۱۴۰۵/۰۸/۱۲ بنویسید.",
                                           "Please write the date as 2026-11-03."))
        return day

    def prepare_value(self, value):
        if isinstance(value, datetime.date):
            return value.isoformat() if is_english() else format_jalali(value, long=False)
        return value


class AppealForm(forms.ModelForm):
    decision_date = DateInputField()

    class Meta:
        model = Appeal
        fields = ["decision", "decision_body", "decision_date", "decision_reference", "grounds",
                  "attachment", "email", "phone"]
        widgets = {
            "grounds": forms.Textarea(attrs={"rows": 10}),
            "email": forms.EmailInput(attrs={"dir": "ltr", "autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"dir": "ltr", "type": "tel", "autocomplete": "tel"}),
            "attachment": forms.ClearableFileInput(attrs={"accept": ",".join(ALLOWED_EXTENSIONS)}),
        }

    def __init__(self, *args, window_days=30, **kwargs):
        super().__init__(*args, **kwargs)
        self.window_days = window_days
        en = is_english()
        labels = {
            "decision": ("به کدام رأی اعتراض دارید؟", "Which decision are you appealing?"),
            "decision_body": ("چه مرجعی رأی را صادر کرد؟", "Who made the decision?"),
            "decision_date": ("تاریخ ابلاغ رأی به شما", "Date you were notified of the decision"),
            "decision_reference": ("شماره یا عنوان نامه رأی (اختیاری)", "Reference of the decision letter (optional)"),
            "grounds": ("دلایل اعتراض", "Grounds for your appeal"),
            "attachment": ("پیوست (اختیاری)", "Attachment (optional)"),
            "email": ("ایمیل برای دریافت پاسخ", "E-mail for the answer"),
            "phone": ("تلفن (اختیاری)", "Phone (optional)"),
        }
        helps = {
            "decision_date": (f"مثلاً ۱۴۰۵/۰۸/۱۲. اعتراض باید ظرف {window_days} روز از ابلاغ ثبت شود.",
                              f"For example 2026-11-03. The appeal must be filed within {window_days} days of notification."),
            "grounds": ("چرا رأی را نادرست می‌دانید؟ واقعیت‌ها، تاریخ‌ها و مدارکی را که کمیسیون یا دبیرخانه در نظر نگرفته‌اند بنویسید.",
                        "Why do you think the decision is wrong? Give the facts, dates and evidence the commission or secretariat did not consider."),
            "attachment": (f"نامه رأی یا مدارک؛ {', '.join(e[1:] for e in ALLOWED_EXTENSIONS)}؛ حداکثر ۱۰ مگابایت",
                           f"The decision letter or evidence; {', '.join(e[1:] for e in ALLOWED_EXTENSIONS)}; up to 10 MB"),
        }
        idx = 1 if en else 0
        for name, field in self.fields.items():
            field.label = labels[name][idx]
            field.help_text = helps.get(name, ("", ""))[idx]
            if en and name == "decision":
                field.choices = [(v, Appeal.DECISION_EN.get(v, l)) for v, l in field.choices]
            if en and name == "decision_body":
                field.choices = [(v, Appeal.BODY_EN.get(v, l)) for v, l in field.choices]
            if en and field.required:
                field.error_messages["required"] = "This field is required."
        self.fields["email"].required = True
        self.fields["decision_date"].widget.attrs.update({"dir": "ltr", "inputmode": "numeric",
                                                          "placeholder": "2026-11-03" if en else "۱۴۰۵/۰۸/۱۲"})

    def clean_decision_date(self):
        day = self.cleaned_data["decision_date"]
        today = timezone.localdate()
        if day > today:
            raise forms.ValidationError(tr("تاریخ ابلاغ نمی‌تواند در آینده باشد.", "The date cannot be in the future."))
        if (today - day).days > self.window_days:
            raise forms.ValidationError(tr(
                f"مهلت {self.window_days} روزه اعتراض به این رأی گذشته است. اگر فکر می‌کنید دلیل موجهی دارید، با دبیرخانه تماس بگیرید.",
                f"The {self.window_days}-day period for appealing this decision has passed. If you have a good reason, "
                "please contact the secretariat.",
            ))
        return day


class PanelComplaintForm(forms.ModelForm):
    """The confidential complaint form, for a member signed in to the panel."""

    class Meta:
        model = Complaint
        fields = ["subject_of_complaint", "category", "description", "attachment"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 8}),
            "attachment": forms.ClearableFileInput(attrs={"accept": ",".join(ALLOWED_ATTACHMENT_EXTENSIONS)}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from contact.forms import HELP, LABELS

        en = is_english()
        idx = 1 if en else 0
        for name, field in self.fields.items():
            field.label = LABELS[name][idx]
            field.help_text = HELP.get(name, ("", ""))[idx]
            if en and name in COMPLAINT_CHOICES_EN:
                field.choices = [(v, COMPLAINT_CHOICES_EN[name].get(v, l)) for v, l in field.choices]
            if en and field.required:
                field.error_messages["required"] = "This field is required."


__all__ = ["AppealForm", "PanelComplaintForm", "MAX_ATTACHMENT_MB"]
