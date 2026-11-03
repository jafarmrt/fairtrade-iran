"""Colours and built-in icons for the ten principles of fair trade.

The colours are the ones WFTO gives each principle in its brand guide (2023),
so the House's list reads like the one used worldwide. The icons are simple
drawings made for this site, not WFTO artwork: WFTO's own principle icons are
"all rights reserved" and need its approval (marketing@wfto.com). Once the
House has that, it can upload the official icon on each principle in the admin.
"""

# WFTO brand guide 2023, principles 1 to 10.
WFTO_COLOURS = (
    "#004e8f",  # 1 night blue
    "#f36e3c",  # 2 orange
    "#b9005b",  # 3 berry
    "#1fb896",  # 4 green
    "#009edb",  # 5 blue
    "#7b2f6a",  # 6 purple
    "#ffce51",  # 7 yellow
    "#ed145a",  # 8 red
    "#009492",  # 9 turquoise
    "#c4d82e",  # 10 lime
)

# key: (admin label, SVG markup inside a 24x24 viewBox, drawn with strokes)
ICONS = {
    "opportunity": ("فرصت برای تولیدکنندگان (پله رو به بالا)",
                    '<path d="M3 20h5v-5h5v-5h5V5h3"/><path d="M15 5h6v6"/>'),
    "transparency": ("شفافیت (چشم)",
                     '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
    "trading": ("تجارت منصفانه (داد و ستد)",
                '<path d="M4 8h14l-3-3"/><path d="M20 16H6l3 3"/>'),
    "payment": ("پرداخت منصفانه (ترازو)",
                '<path d="M12 4v16"/><path d="M8 20h8"/><path d="M5 7h14"/>'
                '<path d="M5 7l-3 6a3 3 0 0 0 6 0z"/><path d="M19 7l-3 6a3 3 0 0 0 6 0z"/>'),
    "children": ("منع کار کودک و کار اجباری (سپر)",
                 '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/><circle cx="12" cy="10" r="2"/>'
                 '<path d="M9 16c.6-1.6 1.7-2.5 3-2.5s2.4.9 3 2.5"/>'),
    "equality": ("برابری و عدم تبعیض (دو نفر)",
                 '<circle cx="8" cy="7" r="2.5"/><circle cx="16" cy="7" r="2.5"/>'
                 '<path d="M3.5 20v-4a4.5 4.5 0 0 1 9 0v4"/><path d="M11.5 20v-4a4.5 4.5 0 0 1 9 0v4"/>'),
    "conditions": ("شرایط کاری مناسب (کلاه ایمنی)",
                   '<path d="M4 17a8 8 0 0 1 16 0"/><path d="M2 17h20v2H2z"/><path d="M10 9V6h4v3"/>'),
    "capacity": ("ظرفیت‌سازی (کتاب باز)",
                 '<path d="M12 6c-2-1.5-5-2-9-2v14c4 0 7 .5 9 2 2-1.5 5-2 9-2V4c-4 0-7 .5-9 2z"/><path d="M12 6v14"/>'),
    "promotion": ("ترویج تجارت عادلانه (بلندگو)",
                  '<path d="M3 10v4h4l9 5V5L7 10z"/><path d="M19 9a4 4 0 0 1 0 6"/><path d="M7 14l1.5 6h3L10 15"/>'),
    "environment": ("محیط زیست (برگ)",
                    '<path d="M5 19C5 10 10 5 20 4c0 10-5 15-14 15z"/><path d="M5 19l8-8"/>'),
}
ICON_ORDER = tuple(ICONS)
ICON_CHOICES = [(key, label) for key, (label, _svg) in ICONS.items()]


def _luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ink_for(hex_colour, dark="#1c1f4a"):
    """White or navy, whichever reads better on the colour."""
    bg = _luminance(hex_colour)
    on_white = 1.05 / (bg + 0.05)
    on_dark = (bg + 0.05) / (_luminance(dark) + 0.05)
    return "#ffffff" if on_white >= on_dark else dark


def default_colour(number):
    return WFTO_COLOURS[(number - 1) % len(WFTO_COLOURS)]


def default_icon(number):
    return ICON_ORDER[(number - 1) % len(ICON_ORDER)]
