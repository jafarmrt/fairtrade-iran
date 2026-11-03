from django import forms
from django.core.validators import MaxValueValidator

from core import money
from core.models import MembershipSettings, is_english
from membership.forms import check_upload

from .models import Decision, Dues
from .services import available_kinds, reason_choices_for


def t(fa, en):
    return en if is_english() else fa


class ReceiptForm(forms.Form):
    """The member sends the receipt of an annual fee payment from the panel."""

    dues = forms.ModelChoiceField(queryset=Dues.objects.none())
    amount = forms.CharField(max_length=30)
    reference = forms.CharField(max_length=100, required=False)
    paid_on_text = forms.CharField(max_length=40, required=False)
    receipt = forms.FileField()
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, member, **kwargs):
        super().__init__(*args, **kwargs)
        payable = member.dues.filter(status=Dues.Status.UNPAID).order_by("year")
        self.fields["dues"].queryset = payable
        first = payable.first()
        if first is not None:
            self.fields["dues"].initial = first.pk
            self.fields["amount"].initial = money.number(first.amount, money.primary_unit(), "en")
        if payable.count() == 1:
            self.fields["dues"].widget = forms.HiddenInput()
        self.fields["dues"].label_from_instance = lambda d: t(f"حق عضویت سال {d.year}", f"Membership fee {d.year}")
        labels = {
            "dues": ("بابت", "For"),
            "amount": (f"مبلغ واریزی ({money.unit_label('fa')})", f"Amount paid ({money.unit_label('en')})"),
            "reference": ("شماره پیگیری یا شماره سند", "Transaction or reference number"),
            "paid_on_text": ("تاریخ واریز", "Date of payment"),
            "receipt": ("تصویر یا فایل رسید", "Photo or file of the receipt"),
            "note": ("توضیح (اختیاری)", "Note (optional)"),
        }
        i = 1 if is_english() else 0
        for name, pair in labels.items():
            self.fields[name].label = pair[i]
        self.fields["paid_on_text"].help_text = t("مثلاً ۱۴۰۵/۰۸/۱۲", "e.g. 2026-11-03")
        for name in ("amount", "reference"):
            self.fields[name].widget.attrs["dir"] = "ltr"
        self.fields["amount"].widget.attrs["inputmode"] = "numeric"

    def clean_amount(self):
        amount = money.parse_amount(self.cleaned_data.get("amount"))
        if not amount:
            raise forms.ValidationError(t("مبلغ واریزی را با عدد بنویسید.", "Please enter the amount paid as a number."))
        return amount

    def clean(self):
        cleaned = super().clean()
        dues, amount = cleaned.get("dues"), cleaned.get("amount")
        if dues is not None and amount is not None and amount < dues.amount:
            self.add_error("amount", t(
                f"مبلغ واریزی از حق عضویت سال {dues.year} ({money.amount(dues.amount, 'fa')}) کمتر است. "
                "اگر بخشی را پرداخته‌اید، با دبیرخانه هماهنگ کنید.",
                f"This is less than the {dues.year} membership fee ({money.amount(dues.amount, 'en')}). "
                "If you paid part of it, please contact the secretariat."))
        return cleaned

    def clean_receipt(self):
        upload = self.cleaned_data.get("receipt")
        check_upload(upload, MembershipSettings.load(), is_english())
        return upload


class StaffPaymentForm(forms.Form):
    """Admin: record a payment received another way, or waive the fee."""

    amount = forms.IntegerField(label="مبلغ دریافتی (ریال)", min_value=1, required=False)
    reference = forms.CharField(label="شماره پیگیری یا شماره سند", max_length=100, required=False)
    note = forms.CharField(label="یادداشت", required=False, widget=forms.Textarea(attrs={"rows": 2}))


class DecisionForm(forms.Form):
    """Admin: a new decision about a member, limited to the user's bodies and the member's status."""

    kind = forms.ChoiceField(label="اقدام")
    reason = forms.ChoiceField(label="دلیل")
    months = forms.IntegerField(label="مدت تعلیق (ماه)", min_value=1, required=False)
    decision_reference = forms.CharField(label="شماره یا تاریخ صورتجلسه", max_length=200, required=False)
    message = forms.CharField(label="پیام به عضو", required=False, widget=forms.Textarea(attrs={"rows": 3}),
                              help_text="در ایمیل عضو و صفحه وضعیت او در پنل اعضا نمایش داده می‌شود")
    internal_note = forms.CharField(label="یادداشت داخلی", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, member, bodies, **kwargs):
        super().__init__(*args, **kwargs)
        kinds = available_kinds(member, bodies)
        self.fields["kind"].choices = [(k, Decision.Kind(k).label) for k in kinds]
        reasons, seen = [], set()
        for k in kinds:
            for value, label in reason_choices_for(k, bodies):
                if value not in seen:
                    seen.add(value)
                    reasons.append((value, label))
        self.fields["reason"].choices = reasons
        self.reasons_by_kind = {k: [v for v, _ in reason_choices_for(k, bodies)] for k in kinds}
        ms = MembershipSettings.load()
        self.fields["months"].max_value = ms.suspension_max_months
        self.fields["months"].validators.append(MaxValueValidator(ms.suspension_max_months))
        self.fields["months"].widget.attrs["max"] = ms.suspension_max_months
        self.fields["months"].initial = ms.suspension_max_months
        self.fields["months"].help_text = f"حداکثر {ms.suspension_max_months} ماه (بند ۱.۷)"

    def clean(self):
        data = super().clean()
        kind, reason = data.get("kind"), data.get("reason")
        if kind and reason and reason not in self.reasons_by_kind.get(kind, []):
            self.add_error("reason", "این دلیل برای این اقدام یا با نقش شما پذیرفته نیست.")
        return data
