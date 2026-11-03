"""Starting wording for wholesale settings; staff edit it in Settings > تنظیمات سفارش عمده."""

INCOTERMS = "\n".join([
    "EXW | Ex Works (you collect from the producer) | تحویل در محل تولیدکننده",
    "FCA | Free Carrier | تحویل به حمل‌کننده",
    "FOB | Free On Board (Bandar Abbas) | تحویل روی کشتی در بندر",
    "CIF | Cost, Insurance and Freight | هزینه، بیمه و کرایه تا بندر مقصد",
    "CPT | Carriage Paid To | کرایه پرداخت‌شده تا مقصد",
    "DAP | Delivered At Place | تحویل در مقصد",
    "DDP | Delivered Duty Paid | تحویل در مقصد با پرداخت عوارض",
    "Not sure | Not sure yet, please advise | هنوز نمی‌دانم، راهنمایی کنید",
])

UNITS = "\n".join([
    "pcs | pieces | عدد",
    "sets | sets | دست",
    "kg | kg | کیلوگرم",
    "m2 | m² | متر مربع",
    "m | metres | متر",
])

PLACEHOLDERS_HELP = ("عبارت‌های داخل {} پر می‌شوند: {name} {company} {code} {country} {items} "
                     "{site_name}")
PRODUCER_PLACEHOLDERS_HELP = ("عبارت‌های داخل {} پر می‌شوند: {name} (نام تولیدکننده) {code} {country} "
                              "{buyer_type} {incoterm} {destination} {needed_by} {items} {panel_url} {site_name}")

BUYER_SUBJECT_EN = "We received your wholesale enquiry ({code})"
BUYER_BODY_EN = """Dear {name},

Thank you for your interest in products from members of the {site_name}.
We have received your enquiry {code} for:

{items}

We are sharing it with the producers concerned and will come back to you with availability,
prices and lead times, usually within a few working days.

With best regards,
{site_name}
"""

BUYER_SUBJECT = "درخواست سفارش عمده شما رسید ({code})"
BUYER_BODY = """{name} گرامی،

از توجه شما به محصولات اعضای {site_name} سپاسگزاریم.
درخواست شما با کد {code} برای این محصولات ثبت شد:

{items}

درخواست را با تولیدکنندگان در میان می‌گذاریم و درباره موجودی، قیمت و زمان آماده‌سازی به‌زودی با شما تماس می‌گیریم.

با احترام،
{site_name}
"""

PRODUCER_SUBJECT = "درخواست سفارش عمده برای محصولات شما ({code})"
PRODUCER_BODY = """{name} گرامی،

یک خریدار از {country} ({buyer_type}) درخواست سفارش عمده‌ای ثبت کرده که محصولات شما در آن است:

{items}

شرایط تحویل: {incoterm}
مقصد: {destination}
زمان مورد نیاز: {needed_by}

لطفاً در پنل اعضا بگویید آیا می‌توانید این سفارش را تأمین کنید، با چه قیمتی و در چه زمانی:
{panel_url}

خانه تجارت عادلانه پاسخ شما را با خریدار در میان می‌گذارد.

{site_name}
"""
