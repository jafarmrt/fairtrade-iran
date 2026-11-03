import re

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_mobile(value):
    """Return an Iranian mobile number as 09xxxxxxxxx, or "" if it is not one."""
    s = re.sub(r"[^\d+]", "", str(value or "").translate(DIGITS))
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    elif s.startswith("98") and len(s) == 12:
        s = "0" + s[2:]
    elif s.startswith("9") and len(s) == 10:
        s = "0" + s
    return s if re.fullmatch(r"09\d{9}", s) else ""


def mobile_list(value):
    """Split a comma/newline separated list and keep the valid, distinct mobiles."""
    if isinstance(value, str):
        value = re.split(r"[,،;\n]+", value)
    seen = []
    for item in value or []:
        number = normalize_mobile(item)
        if number and number not in seen:
            seen.append(number)
    return seen
