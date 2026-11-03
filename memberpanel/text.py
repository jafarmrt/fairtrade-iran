"""Plain text <-> simple rich text, so members edit long descriptions in an ordinary text box."""

import html
import re

_BREAK = re.compile(r"<br\s*/?>", re.I)
_BLOCK_END = re.compile(r"</(p|h[1-6]|li|blockquote|div)>", re.I)
_TAG = re.compile(r"<[^>]+>")


def html_to_text(value):
    if not value:
        return ""
    text = _BREAK.sub("\n", value)
    text = _BLOCK_END.sub("\n\n", text)
    text = html.unescape(_TAG.sub("", text))
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def text_to_html(value):
    value = (value or "").replace("\r\n", "\n").strip()
    if not value:
        return ""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", value) if p.strip()]
    return "".join("<p>" + html.escape(p).replace("\n", "<br/>") + "</p>" for p in paragraphs)
