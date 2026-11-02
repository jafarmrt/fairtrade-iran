from django import forms

from core.models import is_english

from .models import ALLOWED_ATTACHMENT_EXTENSIONS, MAX_ATTACHMENT_MB, Complaint

LABELS = {
    "name": ("نام و نام خانوادگی (اختیاری)", "Your name (optional)"),
    "email": ("ایمیل (اختیاری)", "Email (optional)"),
    "phone": ("تلفن (اختیاری)", "Phone (optional)"),
    "relation": ("شما چه نسبتی با موضوع دارید؟", "How are you involved?"),
    "subject_of_complaint": ("شکایت درباره کیست؟", "Who is the complaint about?"),
    "category": ("موضوع شکایت", "Type of complaint"),
    "description": ("شرح شکایت", "What happened?"),
    "attachment": ("پیوست (اختیاری)", "Attachment (optional)"),
}
HELP = {
    "name": ("می‌توانید بی‌نام شکایت کنید؛ اما بدون راه تماس، کمیسیون نمی‌تواند نتیجه را به شما خبر دهد یا پرسشی بپرسد.",
             "You may stay anonymous, but without a way to reach you the commission cannot ask questions or tell you the outcome."),
    "subject_of_complaint": ("نام عضو، نهاد یا شخص", "Name of the member, organisation or person"),
    "description": ("چه اتفاقی افتاد، کی و کجا؟ هرچه دقیق‌تر بنویسید، رسیدگی ساده‌تر است.",
                    "What happened, when and where? The more detail you give, the easier it is to follow up."),
    "attachment": (
        f"عکس یا سند مرتبط؛ {', '.join(e[1:] for e in ALLOWED_ATTACHMENT_EXTENSIONS)}؛ حداکثر {MAX_ATTACHMENT_MB} مگابایت",
        f"A related photo or document; {', '.join(e[1:] for e in ALLOWED_ATTACHMENT_EXTENSIONS)}; up to {MAX_ATTACHMENT_MB} MB",
    ),
}
CHOICES_EN = {
    "relation": {
        "member": "Member of the House", "buyer": "Buyer", "worker": "Worker or colleague of a member",
        "partner": "Business partner or organisation", "other": "Other",
    },
    "category": {
        "principles": "Breach of fair trade principles", "work": "Working conditions and pay",
        "product": "Product quality or authenticity", "payment": "Payment or transaction",
        "governance": "Conduct of the House's bodies", "other": "Other",
    },
}


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ["name", "email", "phone", "relation", "subject_of_complaint", "category", "description", "attachment"]
        widgets = {
            "email": forms.EmailInput(attrs={"dir": "ltr", "autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"dir": "ltr", "type": "tel", "autocomplete": "tel"}),
            "description": forms.Textarea(attrs={"rows": 8}),
            "attachment": forms.ClearableFileInput(attrs={"accept": ",".join(ALLOWED_ATTACHMENT_EXTENSIONS)}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        en = is_english()
        idx = 1 if en else 0
        for name, field in self.fields.items():
            field.label = LABELS[name][idx]
            field.help_text = HELP.get(name, ("", ""))[idx]
            if en and name in CHOICES_EN:
                field.choices = [(v, CHOICES_EN[name].get(v, label)) for v, label in field.choices]
        if en:
            self.fields["subject_of_complaint"].error_messages["required"] = "This field is required."
            self.fields["description"].error_messages["required"] = "This field is required."
