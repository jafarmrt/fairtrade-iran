from django import forms

from core.models import MembershipSettings, is_english
from membership.forms import check_upload

from .models import Seller


def t(fa, en):
    return en if is_english() else fa


def _labels(form, labels):
    i = 1 if is_english() else 0
    for name, pair in labels.items():
        if name in form.fields:
            form.fields[name].label = pair[i]


class CheckoutForm(forms.Form):
    buyer_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=40)
    email = forms.EmailField(required=False)
    province = forms.CharField(max_length=60, required=False)
    city = forms.CharField(max_length=80)
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    postal_code = forms.CharField(max_length=20, required=False)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    accept_terms = forms.BooleanField()
    # Honeypot: real people leave it empty.
    nickname = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def __init__(self, *args, has_terms=False, **kwargs):
        super().__init__(*args, **kwargs)
        _labels(self, {
            "buyer_name": ("نام و نام خانوادگی", "Full name"),
            "phone": ("تلفن همراه", "Mobile phone"),
            "email": ("ایمیل (برای رسید و پیگیری)", "E-mail (for your receipt and updates)"),
            "province": ("استان", "Province"),
            "city": ("شهر", "City"),
            "address": ("نشانی کامل", "Full address"),
            "postal_code": ("کد پستی", "Postal code"),
            "note": ("توضیح برای تولیدکننده (اختیاری)", "Note for the producer (optional)"),
            "accept_terms": ("شرایط خرید، ارسال و بازگشت کالا را خواندم و می‌پذیرم.",
                             "I have read and accept the terms of sale, shipping and returns.")
            if has_terms else ("اطلاعات بالا درست است.", "The details above are correct."),
        })
        self.fields["nickname"].label = "Leave empty"
        for name in ("phone", "email", "postal_code"):
            self.fields[name].widget.attrs["dir"] = "ltr"
        self.fields["phone"].widget.attrs.update({"autocomplete": "tel", "inputmode": "tel"})
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["buyer_name"].widget.attrs["autocomplete"] = "name"
        self.fields["postal_code"].widget.attrs["inputmode"] = "numeric"

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        digits = "".join(ch for ch in phone if ch.isdigit())
        if len(digits) < 10:
            raise forms.ValidationError(t("شماره تلفن همراه را کامل بنویسید.", "Please enter a full phone number."))
        return phone

    def buyer(self):
        d = self.cleaned_data
        return {k: d.get(k, "") for k in ("buyer_name", "phone", "email", "province", "city", "address",
                                           "postal_code", "note")}


class PaymentInfoForm(forms.Form):
    """The buyer reports a bank transfer for one order."""

    order = forms.IntegerField(widget=forms.HiddenInput())
    reference = forms.CharField(max_length=100, required=False)
    receipt = forms.FileField(required=False)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _labels(self, {
            "reference": ("شماره پیگیری واریز", "Transfer reference number"),
            "receipt": ("تصویر رسید (اختیاری)", "Photo of the receipt (optional)"),
            "note": ("توضیح (اختیاری)", "Note (optional)"),
        })
        self.fields["reference"].widget.attrs["dir"] = "ltr"

    def clean_receipt(self):
        upload = self.cleaned_data.get("receipt")
        check_upload(upload, MembershipSettings.load(), is_english())
        return upload

    def clean(self):
        data = super().clean()
        if not (data.get("reference") or "").strip() and not data.get("receipt"):
            raise forms.ValidationError(t("شماره پیگیری یا تصویر رسید را بفرستید.",
                                          "Send the reference number or a photo of the receipt."))
        return data


class LookupForm(forms.Form):
    code = forms.CharField(max_length=20)
    phone = forms.CharField(max_length=40)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _labels(self, {"code": ("کد سفارش", "Order code"), "phone": ("تلفن همراه هنگام سفارش", "Phone used for the order")})
        for f in self.fields.values():
            f.widget.attrs["dir"] = "ltr"

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class SellerForm(forms.ModelForm):
    """What a member edits about its own selling, in the member panel. Staff set the mode and commission."""

    class Meta:
        model = Seller
        fields = ["account_holder", "bank_name", "card_number", "sheba", "shipping_fee", "free_shipping_over",
                  "prep_days", "shipping_note", "shipping_note_en", "order_mobile", "order_email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _labels(self, {
            "account_holder": ("نام صاحب حساب", "Account holder"),
            "bank_name": ("نام بانک", "Bank"),
            "card_number": ("شماره کارت", "Card number"),
            "sheba": ("شماره شبا", "IBAN (Sheba)"),
            "shipping_fee": ("هزینه ارسال هر سفارش (ریال)", "Shipping cost per order (rials)"),
            "free_shipping_over": ("ارسال رایگان برای خرید بیش از (ریال)", "Free shipping over (rials)"),
            "prep_days": ("آماده‌سازی و ارسال (روز کاری)", "Days to prepare and ship"),
            "shipping_note": ("توضیح ارسال (فارسی)", "Shipping note (Persian)"),
            "shipping_note_en": ("توضیح ارسال (انگلیسی)", "Shipping note (English)"),
            "order_mobile": ("همراه برای پیامک سفارش‌ها", "Mobile for order SMS"),
            "order_email": ("ایمیل دیگر برای خبر سفارش‌ها", "Another e-mail for order updates"),
        })
        hints = {
            "sheba": ("خریداران در پرداخت مستقیم به این حساب واریز می‌کنند؛ در فروش با پرداخت به خانه، سهم شما به آن واریز می‌شود.",
                      "Buyers pay into this account for direct payment; for sales paid to the House, your share is paid here."),
            "free_shipping_over": ("خالی بگذارید اگر ارسال رایگان ندارید.", "Leave empty if you never ship for free."),
            "order_mobile": ("اگر خالی باشد، تلفن پرونده عضویت شما.", "If empty, the phone in your membership file."),
        }
        i = 1 if is_english() else 0
        for name, pair in hints.items():
            self.fields[name].help_text = pair[i]
        for name in ("card_number", "sheba", "shipping_fee", "free_shipping_over", "order_mobile", "order_email",
                     "shipping_note_en"):
            self.fields[name].widget.attrs["dir"] = "ltr"
