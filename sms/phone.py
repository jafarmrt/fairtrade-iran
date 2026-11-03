import re

from core.iran import LATIN_DIGITS as DIGITS, normalize_mobile  # noqa: F401  (one rule for the whole site)


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
