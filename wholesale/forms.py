import time

from django import forms
from django.core import signing

from core.models import is_english

from .models import ProducerShare, WholesaleInquiry, WholesaleSettings

LABELS = {
    "company": ("نام شرکت یا سازمان", "Company or organisation"),
    "contact_name": ("نام شما", "Your name"),
    "email": ("ایمیل", "Email"),
    "phone": ("تلفن یا واتس‌اپ (اختیاری)", "Phone or WhatsApp (optional)"),
    "country": ("کشور", "Country"),
    "city": ("شهر (اختیاری)", "City (optional)"),
    "website": ("وب‌سایت (اختیاری)", "Website (optional)"),
    "buyer_type": ("نوع کسب‌وکار", "Type of business"),
    "incoterm": ("شرایط تحویل", "Delivery terms (Incoterms)"),
    "destination": ("بندر یا شهر مقصد (اختیاری)", "Destination port or city (optional)"),
    "needed_by": ("چه زمانی نیاز دارید؟ (اختیاری)", "When do you need it? (optional)"),
    "other_products": ("محصولات دیگر یا سفارش سفارشی (اختیاری)", "Other products or custom orders (optional)"),
    "message": ("توضیحات (اختیاری)", "Anything else we should know? (optional)"),
}
HELP = {
    "needed_by": ("مثلاً «پیش از اسفند» یا «نمایشگاه بهار»", "For example “before March” or “for our spring catalogue”"),
    "other_products": ("محصولی که در فهرست نیست، رنگ و اندازه دیگر، یا برچسب و بسته‌بندی ویژه",
                       "Something not in the list, other colours or sizes, private label or special packaging"),
    "message": ("کمترین مقدار، بسته‌بندی، گواهی‌های لازم، نمونه و…",
                "Volumes per year, packaging, certificates you need, samples…"),
}
REQUIRED_EN = "This field is required."
SIGNER_SALT = "wholesale-form-started"


def started_token():
    return signing.dumps(time.time(), salt=SIGNER_SALT)


def seconds_since(token):
    try:
        return time.time() - float(signing.loads(token, salt=SIGNER_SALT, max_age=60 * 60 * 24))
    except (signing.BadSignature, TypeError, ValueError):
        return None


class InquiryForm(forms.ModelForm):
    wide_fields = ("other_products", "message")

    class Meta:
        model = WholesaleInquiry
        fields = ["company", "contact_name", "email", "phone", "country", "city", "website", "buyer_type",
                  "incoterm", "destination", "needed_by", "other_products", "message"]
        widgets = {
            "email": forms.EmailInput(attrs={"dir": "ltr", "autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"dir": "ltr", "type": "tel", "autocomplete": "tel"}),
            "website": forms.TextInput(attrs={"dir": "ltr", "autocomplete": "url", "placeholder": "https://"}),
            "company": forms.TextInput(attrs={"autocomplete": "organization"}),
            "contact_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "country": forms.TextInput(attrs={"autocomplete": "country-name"}),
            "city": forms.TextInput(attrs={"autocomplete": "address-level2"}),
            "other_products": forms.Textarea(attrs={"rows": 3}),
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, settings=None, **kwargs):
        super().__init__(*args, **kwargs)
        settings = settings or WholesaleSettings.load()
        en = is_english()
        idx = 1 if en else 0
        incoterms = settings.incoterm_choices(en)
        self.fields["incoterm"] = forms.ChoiceField(
            choices=[("", "—")] + incoterms, required=False) if incoterms else forms.CharField(
            required=False, max_length=60)
        for name, field in self.fields.items():
            if name in LABELS:
                field.label = LABELS[name][idx]
                field.help_text = HELP.get(name, ("", ""))[idx]
            if en and field.required:
                field.error_messages["required"] = REQUIRED_EN
        if en:
            self.fields["buyer_type"].choices = [
                (v, WholesaleInquiry.BUYER_TYPE_EN.get(v, label)) for v, label in self.fields["buyer_type"].choices
            ]
            self.fields["email"].error_messages["invalid"] = "Enter a valid email address."


class ReplyForm(forms.ModelForm):
    """The producer's answer in the member panel."""

    class Meta:
        model = ProducerShare
        fields = ["status", "price_quote", "lead_time", "reply"]
        widgets = {"reply": forms.Textarea(attrs={"rows": 4})}

    LABELS = {
        "status": ("می‌توانید این سفارش را تأمین کنید؟", "Can you supply this order?"),
        "price_quote": ("قیمت پیشنهادی", "Your price"),
        "lead_time": ("زمان آماده‌سازی", "Lead time"),
        "reply": ("توضیح برای خانه", "Notes for the House"),
    }
    HELP = {
        "price_quote": ("قیمت هر واحد یا جمع کل، با ارز؛ مثلاً «۱۲ یورو هر عدد، تحویل در کارگاه»",
                        "Per unit or in total, with the currency; e.g. “EUR 12 per piece, ex works”"),
        "lead_time": ("مثلاً «۶ هفته پس از تأیید سفارش»", "For example “6 weeks after the order is confirmed”"),
        "reply": ("کمترین مقدار، رنگ‌ها و اندازه‌های موجود، بسته‌بندی، نمونه و…",
                  "Minimum quantity, available colours and sizes, packaging, samples…"),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        en = is_english()
        idx = 1 if en else 0
        choices = [(v, ProducerShare.STATUS_EN[v] if en else label)
                   for v, label in ProducerShare.Status.choices if v in ProducerShare.ANSWERED]
        self.fields["status"] = forms.ChoiceField(choices=choices, widget=forms.RadioSelect,
                                                  label=self.LABELS["status"][idx])
        if self.instance.status in ProducerShare.ANSWERED:
            self.initial["status"] = self.instance.status
        for name, field in self.fields.items():
            field.label = self.LABELS[name][idx]
            field.help_text = self.HELP.get(name, ("", ""))[idx]
