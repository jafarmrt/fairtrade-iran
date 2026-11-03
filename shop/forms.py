from django import forms

from core import iran
from core.models import MembershipSettings, is_english
from membership.forms import check_upload

from .models import Seller, ShippingOption


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
    province = forms.ChoiceField(required=False)
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
        self.fields["postal_code"].widget.attrs.update({"inputmode": "numeric", "autocomplete": "postal-code"})
        self.fields["phone"].widget.attrs["placeholder"] = "09123456789"
        en = is_english()
        self.fields["province"].choices = [("", "—")] + iran.province_choices(en)
        self.fields["province"].required = not en
        self.fields["postal_code"].required = not en

    def clean_phone(self):
        # Orders ship inside Iran, so the buyer's mobile is Iranian (SMS updates go to it).
        return iran.clean_mobile(self.cleaned_data["phone"], is_english(), allow_foreign=is_english())

    def clean_postal_code(self):
        return iran.clean_postal_code(self.cleaned_data["postal_code"], is_english())

    def clean_buyer_name(self):
        return iran.normalize_text(self.cleaned_data["buyer_name"])

    def clean_city(self):
        return iran.normalize_text(self.cleaned_data["city"])

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
            "shipping_note": ("مثلاً «ارسال با پست پیشتاز به سراسر ایران»",
                              "For example “Express post to all of Iran”, in Persian."),
            "shipping_note_en": ("", "For foreign visitors, if you ship abroad."),
            "order_email": ("جز مدیران پنل این عضو، سفارش‌ها به این نشانی هم خبر داده می‌شود",
                            "Besides this member's panel managers, order updates also go to this address."),
        }
        i = 1 if is_english() else 0
        for name, pair in hints.items():
            self.fields[name].help_text = pair[i]
        for name in ("card_number", "sheba", "shipping_fee", "free_shipping_over", "order_mobile", "order_email",
                     "shipping_note_en"):
            self.fields[name].widget.attrs["dir"] = "ltr"
        self.fields["card_number"].widget.attrs.update({"inputmode": "numeric", "placeholder": "6037 9911 2345 6789"})
        self.fields["sheba"].widget.attrs["placeholder"] = "IR12 0170 0000 0000 0000 0000 00"
        self.fields["order_mobile"].widget.attrs.update({"inputmode": "tel", "placeholder": "09123456789"})

    def clean_card_number(self):
        return iran.clean_card_number(self.cleaned_data["card_number"], is_english())

    def clean_sheba(self):
        return iran.clean_sheba(self.cleaned_data["sheba"], is_english())

    def clean_order_mobile(self):
        return iran.clean_mobile(self.cleaned_data["order_mobile"], is_english())


class ShippingOptionForm(forms.ModelForm):
    class Meta:
        model = ShippingOption
        fields = ["name", "name_en", "fee", "delivery_time", "delivery_time_en", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _labels(self, {
            "name": ("نام روش", "Method (Persian)"),
            "name_en": ("نام انگلیسی", "Method (English)"),
            "fee": ("هزینه (ریال)", "Cost (rials)"),
            "delivery_time": ("زمان رسیدن", "Delivery time (Persian)"),
            "delivery_time_en": ("زمان رسیدن (انگلیسی)", "Delivery time (English)"),
            "active": ("فعال", "Active"),
        })
        self.fields["name"].widget.attrs["placeholder"] = t("پست پیشتاز", "پست پیشتاز")
        self.fields["delivery_time"].widget.attrs["placeholder"] = t("۲ تا ۴ روز کاری", "۲ تا ۴ روز کاری")
        for name in ("fee", "name_en", "delivery_time_en"):
            self.fields[name].widget.attrs["dir"] = "ltr"


ShippingOptionFormSet = forms.inlineformset_factory(
    Seller, ShippingOption, form=ShippingOptionForm, extra=1, can_delete=True, max_num=6, validate_max=True)
