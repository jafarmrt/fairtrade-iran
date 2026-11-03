from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import ValidationError
from wagtail.images.fields import WagtailImageField

from core.models import is_english
from members.models import Member, Region
from products.models import Category, Product

from .text import html_to_text, text_to_html

# Labels and hints shown to members: (Persian, English).
LABELS = {
    "name": ("نام مجموعه (فارسی)", "Name (Persian)"),
    "name_en": ("نام مجموعه (انگلیسی)", "Name (English)"),
    "region": ("استان", "Province"),
    "city": ("شهر یا روستا (فارسی)", "Town or village (Persian)"),
    "city_en": ("شهر یا روستا (انگلیسی)", "Town or village (English)"),
    "summary": ("معرفی کوتاه (فارسی)", "Short introduction (Persian)"),
    "summary_en": ("معرفی کوتاه (انگلیسی)", "Short introduction (English)"),
    "story": ("داستان و معرفی کامل (فارسی)", "Full story (Persian)"),
    "story_en": ("داستان و معرفی کامل (انگلیسی)", "Full story (English)"),
    "logo_upload": ("لوگوی تازه", "New logo"),
    "remove_logo": ("حذف لوگوی فعلی", "Remove the current logo"),
    "cover_upload": ("تصویر اصلی تازه", "New main photo"),
    "remove_cover": ("حذف تصویر اصلی فعلی", "Remove the current main photo"),
    "instagram_url": ("نشانی اینستاگرام", "Instagram address"),
    "website_url": ("وب‌سایت یا فروشگاه اینترنتی", "Website or online shop"),
    "public_phone": ("تلفن عمومی", "Public phone"),
    "public_email": ("ایمیل عمومی", "Public e-mail"),
    # products
    "category": ("دسته‌بندی", "Category"),
    "description": ("توضیحات کامل (فارسی)", "Full description (Persian)"),
    "description_en": ("توضیحات کامل (انگلیسی)", "Full description (English)"),
    "price": ("قیمت (ریال)", "Price (rials)"),
    "price_note": ("توضیح قیمت (فارسی)", "Price note (Persian)"),
    "price_note_en": ("توضیح قیمت (انگلیسی)", "Price note (English)"),
    "in_stock": ("موجود است", "In stock"),
    "purchase_url": ("لینک خرید مستقیم", "Direct purchase link"),
    "is_published": ("در سایت نمایش داده شود", "Show on the website"),
    "new_images": ("افزودن تصویر", "Add photos"),
}
HELP = {
    "name_en": ("اگر خالی باشد، در نسخه انگلیسی سایت نمایش داده نمی‌شوید.",
                "If empty, you are not listed on the English site."),
    "summary": ("یک جمله برای کارت شما در فهرست اعضا.", "One sentence for your card in the members list."),
    "story": ("برای پاراگراف تازه یک خط خالی بگذارید.", "Leave an empty line between paragraphs."),
    "story_en": ("برای پاراگراف تازه یک خط خالی بگذارید.", "Leave an empty line between paragraphs."),
    "cover_upload": ("عکس کارگاه، تولیدکنندگان یا محصولات؛ بهتر است افقی باشد.",
                     "A photo of your workshop, makers or products; landscape works best."),
    "instagram_url": ("مثلاً https://instagram.com/yourpage", "e.g. https://instagram.com/yourpage"),
    "website_url": ("دکمه «خرید از تولیدکننده» به اینجا می‌رود.",
                    "The \"Buy from the producer\" button links here."),
    "product_name_en": ("اگر خالی باشد، این محصول در نسخه انگلیسی سایت نمایش داده نمی‌شود.",
                        "If empty, this product is not shown on the English site."),
    "price": ("اگر خالی باشد قیمت نمایش داده نمی‌شود.", "Leave empty to hide the price."),
    "price_note": ("مثلاً «قیمت بر اساس سفارش» یا «هر کیلوگرم».", "e.g. \"price on request\" or \"per kilo\"."),
    "purchase_url": ("صفحه همین محصول در فروشگاه یا اینستاگرام شما. اگر خالی باشد، وب‌سایت یا اینستاگرام شما استفاده می‌شود.",
                     "This product's page in your shop or Instagram. If empty, your website or Instagram is used."),
    "description": ("جنس، ابعاد، روش ساخت و داستان محصول. برای پاراگراف تازه یک خط خالی بگذارید.",
                    "Material, size, how it is made and its story. Leave an empty line between paragraphs."),
}


def _bilingual(form, help_overrides=None):
    i = 1 if is_english() else 0
    help_overrides = help_overrides or {}
    for name, field in form.fields.items():
        if name in LABELS:
            field.label = LABELS[name][i]
        key = help_overrides.get(name, name)
        field.help_text = HELP[key][i] if key in HELP else ""


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(WagtailImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/*"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(d, initial) for d in data if d]
        return [single(data, initial)] if data else []


def image_field():
    return WagtailImageField(required=False, widget=forms.ClearableFileInput(attrs={"accept": "image/*"}))


class RichTextAsPlainMixin:
    """Shows rich text model fields as plain text boxes; saves them back only when the text changed,
    so formatting the secretariat added stays as long as the member does not touch that field."""

    rich_fields = ()

    def setup_rich_fields(self):
        for name in self.rich_fields:
            initial = html_to_text(getattr(self.instance, name, ""))
            self.fields[f"{name}_text"] = forms.CharField(
                required=False, initial=initial, widget=forms.Textarea(attrs={"rows": 8}),
            )
            self.fields[f"{name}_text"].label = LABELS[name][1 if is_english() else 0]
            hint = HELP.get(name) or HELP.get("story")
            self.fields[f"{name}_text"].help_text = hint[1 if is_english() else 0]

    def apply_rich_fields(self, instance):
        for name in self.rich_fields:
            new = self.cleaned_data.get(f"{name}_text", "")
            if new.strip() != html_to_text(getattr(instance, name, "")).strip():
                setattr(instance, name, text_to_html(new))


class ProfileForm(RichTextAsPlainMixin, forms.ModelForm):
    rich_fields = ("story", "story_en")

    logo_upload = image_field()
    remove_logo = forms.BooleanField(required=False)
    cover_upload = image_field()
    remove_cover = forms.BooleanField(required=False)

    class Meta:
        model = Member
        fields = ["name", "name_en", "region", "city", "city_en", "summary", "summary_en",
                  "instagram_url", "website_url", "public_phone", "public_email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_rich_fields()
        self.fields["region"].queryset = Region.objects.all()
        if is_english():
            self.fields["region"].label_from_instance = lambda r: r.name_en or r.name
        _bilingual(self)
        for name in ("story_text", "story_en_text"):
            self.fields[name].help_text = HELP["story"][1 if is_english() else 0]
        for name in ("instagram_url", "website_url", "public_email", "public_phone", "name_en",
                     "city_en", "summary_en"):
            self.fields[name].widget.attrs.setdefault("dir", "ltr")
        self.fields["story_en_text"].widget.attrs["dir"] = "ltr"

    # Field groups for the template: (Persian heading, English heading, field names)
    groups = [
        ("معرفی", "About", ["name", "summary", "story_text", "region", "city"]),
        ("انگلیسی", "English", ["name_en", "summary_en", "story_en_text", "city_en"]),
        ("تصاویر", "Images", ["logo_upload", "remove_logo", "cover_upload", "remove_cover"]),
        ("راه‌های ارتباط و خرید", "Contact and buying", ["instagram_url", "website_url", "public_phone", "public_email"]),
    ]

    def grouped(self):
        i = 1 if is_english() else 0
        return [(g[i], [self[n] for n in g[2]]) for g in self.groups]


class ProductForm(RichTextAsPlainMixin, forms.ModelForm):
    rich_fields = ("description", "description_en")

    new_images = MultipleImageField(required=False)

    class Meta:
        model = Product
        fields = ["name", "name_en", "category", "summary", "summary_en", "price", "price_note",
                  "price_note_en", "in_stock", "purchase_url", "is_published"]

    def __init__(self, *args, max_images=6, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_images = max_images
        self.setup_rich_fields()
        if is_english():
            self.fields["category"].label_from_instance = lambda c: c.name_en or c.name
        self.fields["category"].queryset = Category.objects.all()
        _bilingual(self, {"name_en": "product_name_en", "summary": "_none"})
        for name in ("description_text", "description_en_text"):
            self.fields[name].help_text = HELP["description"][1 if is_english() else 0]
        i = 1 if is_english() else 0
        self.fields["name"].label = ("نام محصول (فارسی)", "Product name (Persian)")[i]
        self.fields["name_en"].label = ("نام محصول (انگلیسی)", "Product name (English)")[i]
        self.fields["summary"].label = ("توضیح کوتاه (فارسی)", "Short description (Persian)")[i]
        self.fields["summary_en"].label = ("توضیح کوتاه (انگلیسی)", "Short description (English)")[i]
        for name in ("name_en", "summary_en", "price_note_en", "purchase_url"):
            self.fields[name].widget.attrs.setdefault("dir", "ltr")
        self.fields["description_en_text"].widget.attrs["dir"] = "ltr"

    groups = [
        ("محصول", "Product", ["name", "category", "summary", "description_text"]),
        ("انگلیسی", "English", ["name_en", "summary_en", "description_en_text", "price_note_en"]),
        ("قیمت و فروش", "Price and sales", ["price", "price_note", "in_stock", "purchase_url", "is_published"]),
    ]

    def grouped(self):
        i = 1 if is_english() else 0
        return [(g[i], [self[n] for n in g[2]]) for g in self.groups]

    def clean(self):
        cleaned = super().clean()
        existing = self.instance.images.count() if self.instance.pk else 0
        removing = len(self.data.getlist("remove_image")) if hasattr(self.data, "getlist") else 0
        total = existing - removing + len(cleaned.get("new_images") or [])
        if self.max_images and total > self.max_images:
            raise ValidationError(
                (f"Up to {self.max_images} photos per product." if is_english()
                 else f"هر محصول حداکثر {self.max_images} تصویر می‌تواند داشته باشد.")
            )
        return cleaned


class PanelPasswordResetForm(PasswordResetForm):
    """Also reaches accounts that have no password yet (created by the secretariat or by an invitation)."""

    def get_users(self, email):
        User = get_user_model()
        return (u for u in User._default_manager.filter(email__iexact=email, is_active=True) if u.email)
