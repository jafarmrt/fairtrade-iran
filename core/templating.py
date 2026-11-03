"""Fill the {placeholders} in e-mail and SMS texts that staff edit in the admin."""

import re

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def fill(text, values):
    """
    Replace {name} with values["name"]. Unknown names stay as they are, and
    stray braces or other {…} forms are left alone, so a typo in an admin
    text never stops an e-mail or exposes anything beyond the given values.
    """
    if not text:
        return ""
    values = values or {}

    def sub(match):
        key = match.group(1)
        if key not in values:
            return match.group(0)
        value = values[key]
        return "" if value is None else str(value)

    return PLACEHOLDER.sub(sub, text)
