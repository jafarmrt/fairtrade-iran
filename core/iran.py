"""
Iranian input rules in one place: Persian/Arabic digits, Arabic ي/ك, and
the checks for mobile numbers, national ID, legal-entity ID, postal code,
Sheba (IBAN) and bank card numbers. Forms call the clean_* helpers; they
return the value in the form we store (Latin digits, no spaces) or raise
ValidationError with a Persian or English message.
"""

import re

from django.core.exceptions import ValidationError

LATIN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
# Arabic letters that Persian keyboards and Word documents often produce.
PERSIAN_LETTERS = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "هٔ", "ة": "ه"})
ARABIC_LETTERS = str.maketrans({"ی": "ي", "ک": "ك"})


def latin_digits(value):
    return str(value or "").translate(LATIN_DIGITS)


def persian_digits(value):
    return str(value).translate(PERSIAN_DIGITS)


def normalize_text(value):
    """Persian letters (ی، ک) and Latin digits; trims surrounding spaces."""
    return str(value or "").translate(PERSIAN_LETTERS).translate(LATIN_DIGITS).strip()


def search_variants(query):
    """The query as typed with Persian letters, plus its Arabic-letter spelling, for icontains searches."""
    q = normalize_text(query)
    variants = [q]
    arabic = q.translate(ARABIC_LETTERS)
    if arabic != q:
        variants.append(arabic)
    return variants


def only_digits(value):
    return re.sub(r"[^0-9]", "", latin_digits(value))


def _t(fa, en, english):
    return en if english else fa


# ---- mobile ----

def normalize_mobile(value):
    """An Iranian mobile number as 09xxxxxxxxx, or "" if it is not one."""
    s = re.sub(r"[^0-9+]", "", latin_digits(value))
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    elif s.startswith("98") and len(s) == 12:
        s = "0" + s[2:]
    elif s.startswith("9") and len(s) == 10:
        s = "0" + s
    return s if re.fullmatch(r"09[0-9]{9}", s) else ""


def clean_mobile(value, english=False, allow_foreign=False):
    """09xxxxxxxxx for an Iranian mobile; with allow_foreign, also +<country><number>."""
    value = (value or "").strip()
    if not value:
        return ""
    mobile = normalize_mobile(value)
    if mobile:
        return mobile
    if allow_foreign:
        s = re.sub(r"[^0-9+]", "", latin_digits(value))
        if s.startswith("00"):
            s = "+" + s[2:]
        if re.fullmatch(r"\+[1-9][0-9]{7,14}", s) and not s.startswith("+98"):
            return s
        raise ValidationError(_t(
            "شماره موبایل را مثل ۰۹۱۲۳۴۵۶۷۸۹ بنویسید؛ شمارهٔ خارج از ایران را با + و کد کشور.",
            "Write the mobile as 09123456789, or a number outside Iran with + and the country code.", english))
    raise ValidationError(_t("شماره موبایل باید ۱۱ رقم باشد و با ۰۹ شروع شود.",
                             "The mobile number must have 11 digits and start with 09.", english))


def same_phone(a, b):
    """Whether two phone numbers are the same, whatever digits or format they were typed in."""
    na, nb = normalize_mobile(a), normalize_mobile(b)
    if na and nb:
        return na == nb
    da, db = only_digits(a), only_digits(b)
    return bool(da) and da == db


# ---- national ID (کد ملی) and legal-entity ID (شناسه ملی) ----

def is_national_id(value):
    s = only_digits(value)
    if not re.fullmatch(r"[0-9]{10}", s) or len(set(s)) == 1:
        return False
    total = sum(int(s[i]) * (10 - i) for i in range(9))
    r = total % 11
    return int(s[9]) == (r if r < 2 else 11 - r)


def is_legal_id(value):
    """شناسه ملی of a company or organisation: 11 digits with a check digit."""
    s = only_digits(value)
    if not re.fullmatch(r"[0-9]{11}", s) or len(set(s)) == 1:
        return False
    d = int(s[9]) + 2
    weights = [29, 27, 23, 19, 17, 29, 27, 23, 19, 17]
    r = sum((int(s[i]) + d) * weights[i] for i in range(10)) % 11
    return int(s[10]) == (0 if r == 10 else r)


def clean_national_id(value, english=False):
    if not (value or "").strip():
        return ""
    if not is_national_id(value):
        raise ValidationError(_t("کد ملی معتبر نیست.", "This national ID is not valid.", english))
    return only_digits(value)


def clean_legal_id(value, english=False):
    if not (value or "").strip():
        return ""
    if not is_legal_id(value):
        raise ValidationError(_t("شناسه ملی معتبر نیست.", "This national ID of the organisation is not valid.",
                                 english))
    return only_digits(value)


# ---- postal code ----

def clean_postal_code(value, english=False):
    if not (value or "").strip():
        return ""
    s = only_digits(value)
    if len(s) != 10:
        raise ValidationError(_t("کد پستی باید ۱۰ رقم باشد.", "The postal code must have 10 digits.", english))
    return s


# ---- Sheba (IBAN) and bank card ----

def normalize_sheba(value):
    s = re.sub(r"[\s\-‌_]", "", latin_digits(value)).upper()
    if s.startswith("IR"):
        s = s[2:]
    return "IR" + s if re.fullmatch(r"[0-9]{24}", s) else ""


def is_sheba(value):
    s = normalize_sheba(value)
    if not s:
        return False
    rearranged = s[4:] + "1827" + s[2:4]
    return int(rearranged) % 97 == 1


def clean_sheba(value, english=False):
    if not (value or "").strip():
        return ""
    if not normalize_sheba(value):
        raise ValidationError(_t("شماره شبا ۲۴ رقم بعد از IR دارد.",
                                 "An Iranian IBAN (Sheba) has 24 digits after IR.", english))
    if not is_sheba(value):
        raise ValidationError(_t("شماره شبا معتبر نیست.", "This IBAN (Sheba) is not valid.", english))
    return normalize_sheba(value)


def is_card_number(value):
    s = only_digits(value)
    if len(s) != 16:
        return False
    total = 0
    for i, ch in enumerate(s):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def clean_card_number(value, english=False):
    if not (value or "").strip():
        return ""
    s = only_digits(value)
    if len(s) != 16:
        raise ValidationError(_t("شماره کارت باید ۱۶ رقم باشد.", "The card number must have 16 digits.", english))
    if not is_card_number(s):
        raise ValidationError(_t("شماره کارت معتبر نیست.", "This card number is not valid.", english))
    return s


def format_card(value):
    s = only_digits(value)
    return " ".join(s[i:i + 4] for i in range(0, len(s), 4)) if len(s) == 16 else value


# ---- provinces ----

PROVINCES = [
    ("آذربایجان شرقی", "East Azerbaijan"), ("آذربایجان غربی", "West Azerbaijan"), ("اردبیل", "Ardabil"),
    ("اصفهان", "Isfahan"), ("البرز", "Alborz"), ("ایلام", "Ilam"), ("بوشهر", "Bushehr"), ("تهران", "Tehran"),
    ("چهارمحال و بختیاری", "Chaharmahal and Bakhtiari"), ("خراسان جنوبی", "South Khorasan"),
    ("خراسان رضوی", "Razavi Khorasan"), ("خراسان شمالی", "North Khorasan"), ("خوزستان", "Khuzestan"),
    ("زنجان", "Zanjan"), ("سمنان", "Semnan"), ("سیستان و بلوچستان", "Sistan and Baluchestan"), ("فارس", "Fars"),
    ("قزوین", "Qazvin"), ("قم", "Qom"), ("کردستان", "Kurdistan"), ("کرمان", "Kerman"),
    ("کرمانشاه", "Kermanshah"), ("کهگیلویه و بویراحمد", "Kohgiluyeh and Boyer-Ahmad"), ("گلستان", "Golestan"),
    ("گیلان", "Gilan"), ("لرستان", "Lorestan"), ("مازندران", "Mazandaran"), ("مرکزی", "Markazi"),
    ("هرمزگان", "Hormozgan"), ("همدان", "Hamadan"), ("یزد", "Yazd"),
]


def province_choices(english=False):
    """Choices stored with the Persian name, shown in the page language."""
    return [(fa, en if english else fa) for fa, en in PROVINCES]


def clean_bank_fields(obj, card="card_number", sheba="sheba"):
    """For a model's clean(): check and normalise its card and Sheba fields (admin forms)."""
    errors = {}
    for field, cleaner in ((card, clean_card_number), (sheba, clean_sheba)):
        try:
            setattr(obj, field, cleaner(getattr(obj, field, "")))
        except ValidationError as e:
            errors[field] = e.messages
    if errors:
        raise ValidationError(errors)


def text_search(query, *fields):
    """A Q matching `query` in any of `fields`, whichever of ی/ي, ک/ك and digit forms were used."""
    from django.db.models import Q

    condition = Q()
    for variant in search_variants(query):
        for field in fields:
            condition |= Q(**{f"{field}__icontains": variant})
    return condition
