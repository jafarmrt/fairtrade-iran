"""
Read a gettext .po file and write the .mo file Django loads, with the
standard library only, so `manage.py build_translations` works on any
machine (Django's compilemessages needs GNU gettext installed).

Used for locale/fa/, where we complete and correct Wagtail's Persian
admin translations (see locale/README.md).
"""

import ast
import struct


def _unquote(line):
    return ast.literal_eval(line)


def parse(text):
    """Return a list of dicts: ctxt, id, plural, str (a string, or a list for plurals), flags."""
    entries, current, last_key = [], None, None

    def finish():
        if current is not None and "id" in current:
            entries.append(current)

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            finish()
            current, last_key = None, None
            continue
        if line.startswith("#,"):
            current = current or {}
            current.setdefault("flags", []).extend(f.strip() for f in line[2:].split(","))
            continue
        if line.startswith("#"):
            current = current or {}
            continue
        current = current or {}
        if line.startswith('"'):
            value = _unquote(line)
            if last_key.startswith("str["):
                index = int(last_key[4:-1])
                current["str"][index] += value
            else:
                current[last_key] += value
            continue
        keyword, _, rest = line.partition(" ")
        if keyword == "msgctxt":
            if "id" in current:  # a new entry without a blank line before it
                finish()
                current = {}
            current["ctxt"], last_key = _unquote(rest), "ctxt"
        elif keyword == "msgid":
            if "id" in current:
                finish()
                current = {}
            current["id"], last_key = _unquote(rest), "id"
        elif keyword == "msgid_plural":
            current["plural"], last_key = _unquote(rest), "plural"
        elif keyword == "msgstr":
            current["str"], last_key = _unquote(rest), "str"
        elif keyword.startswith("msgstr["):
            index = int(keyword[7:-1])
            if not isinstance(current.get("str"), list):
                current["str"] = []
            while len(current["str"]) <= index:
                current["str"].append("")
            current["str"][index], last_key = _unquote(rest), f"str[{index}]"
        else:
            raise ValueError(f"cannot read .po line: {raw!r}")
    finish()
    return entries


def mo_bytes(entries):
    """GNU .mo content for parsed entries (fuzzy and untranslated ones are left out)."""
    pairs = []
    for e in entries:
        if "fuzzy" in e.get("flags", ()):
            continue
        value = e.get("str", "")
        if isinstance(value, list):
            if not all(value):
                continue
            value = "\x00".join(value)
        if not value:
            continue
        key = e["id"]
        if e.get("plural") is not None:
            key += "\x00" + e["plural"]
        if e.get("ctxt") is not None:
            key = e["ctxt"] + "\x04" + key
        pairs.append((key.encode(), value.encode()))
    pairs.sort()
    count = len(pairs)
    keys_start = 7 * 4
    values_start = keys_start + count * 8
    data_start = values_start + count * 8
    key_table, value_table, data = [], [], b""
    offset = data_start
    for key, _ in pairs:
        key_table.append((len(key), offset))
        data += key + b"\x00"
        offset += len(key) + 1
    for _, value in pairs:
        value_table.append((len(value), offset))
        data += value + b"\x00"
        offset += len(value) + 1
    header = struct.pack("<7I", 0x950412DE, 0, count, keys_start, values_start, 0, 0)
    tables = b"".join(struct.pack("<2I", *pair) for pair in key_table + value_table)
    return header + tables + data
