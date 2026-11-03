"""
Starting text for the site. Persian text comes from the house's own
introduction and the governance document (version 2, Mehr 1405); English
is a translation for the PR working group to review.
"""

import json


def stream(*blocks):
    return json.dumps([{"type": t, "value": v} for t, v in blocks], ensure_ascii=False)


HOME = {
    "fa": {
        "title": "خانه تجارت عادلانه ایران",
        "slug": "fa",
        "hero_title": "تجارت عادلانه، فرصتی برابر برای تولیدکنندگان محلی",
        "hero_text": (
            "خانه تجارت عادلانه ایران یک شبکه ملی برای ترویج، حمایت و توسعه اصول تجارت عادلانه است؛ "
            "از کسب‌وکارهای خرد و جوامع محلی پشتیبانی می‌کنیم تا در محیطی منصفانه و پایدار کار کنند "
            "و محصولاتشان به دست مصرف‌کنندگان آگاه برسد."
        ),
        "hero_cta_text": "آشنایی با خانه",
        "intro": (
            "<p>ما دو بال داریم: <b>ترویج اصول ده‌گانه تجارت عادلانه</b> برای شناخت و قوام عملی این اصول، "
            "و <b>تسهیلگری فروش</b> محصولات اعضا در بازارهای داخلی و بین‌المللی.</p>"
        ),
        "body": stream((
            "cards",
            {
                "heading": "چرا عضو خانه تجارت عادلانه شویم؟",
                "cards": [
                    {"title": "تجمیع توان و منابع", "text": "بهره‌مندی از نمایشگاه‌ها، آموزش‌ها و امکانات مشترکی که دسترسی به آن‌ها به‌تنهایی دشوار است."},
                    {"title": "نشان معتبر", "text": "معرفی مؤثرتر در جامعه و جلب اعتماد عمومی با استفاده از نشان تجارت عادلانه."},
                    {"title": "بازارهای تازه", "text": "اتصال به مصرف‌کنندگان حساس به اثرات اجتماعی و زیست‌محیطی و فرصت‌های صادراتی."},
                    {"title": "شبکه‌سازی و یادگیری", "text": "تبادل تجربه، نوآوری و همکاری‌های مشترک میان اعضا."},
                    {"title": "کاهش هزینه و ریسک", "text": "تقسیم بخشی از هزینه‌های تبلیغات، آموزش و تأمین مواد اولیه از راه سازوکارهای جمعی."},
                    {"title": "تغییر اجتماعی", "text": "نقش‌آفرینی در ترویج مصرف آگاهانه و حرکت به سوی اقتصادی انسانی‌تر، سبزتر و منصفانه‌تر."},
                ],
            },
        )),
    },
    "en": {
        "title": "Fair Trade House of Iran",
        "slug": "en",
        "hero_title": "Fair trade, an equal chance for local producers",
        "hero_text": (
            "The Fair Trade House of Iran is a national network that promotes, supports and develops "
            "the principles of fair trade. We support small businesses and local communities so they "
            "can work in fair, sustainable conditions and reach conscious consumers."
        ),
        "hero_cta_text": "About the House",
        "intro": (
            "<p>Our work has two wings: <b>promoting the ten principles of fair trade</b> so they are "
            "understood and practised, and <b>facilitating sales</b> of our members' products in "
            "domestic and international markets.</p>"
        ),
        "body": stream((
            "cards",
            {
                "heading": "Why join the Fair Trade House?",
                "cards": [
                    {"title": "Pooled strength", "text": "Shared exhibitions, training and resources that are hard to reach alone."},
                    {"title": "A trusted mark", "text": "Use of the fair trade mark to build public trust and visibility."},
                    {"title": "New markets", "text": "Connection with socially and environmentally conscious buyers, and export opportunities."},
                    {"title": "Network and learning", "text": "Exchange of experience, innovation and joint projects among members."},
                    {"title": "Lower costs and risks", "text": "Shared mechanisms for advertising, training and sourcing raw materials."},
                    {"title": "Social change", "text": "A role in promoting conscious consumption and a fairer, greener economy."},
                ],
            },
        )),
    },
}

_ABOUT_FA = stream(
    ("paragraph",
     "<p>«خانه تجارت عادلانه ایران» یک شبکه ملی برای ترویج، حمایت و توسعه اصول تجارت عادلانه در ایران است. "
     "طرح ایجاد این شبکه در زمستان ۱۴۰۳ بر پایه شناخت و نیاز کسب‌وکارهای خرد برای فرهنگ‌سازی و تسهیلگری فروش "
     "براساس اصول ده‌گانه تجارت عادلانه توسط «خانه هفت دست» و «گروه پاپیتال» مطرح شد. گروه‌هایی که فعالیت یا "
     "دغدغه مرتبط با این اصول داشتند شناسایی و برای پایه‌گذاری این مجموعه دعوت شدند.</p>"),
    ("paragraph",
     "<p>هفت گروه تولیدی شامل فرآورده‌های بومی میناب (ارموز)، گروه زیورآلات پاپیتال، محصولات بومی جنوب فارس "
     "(پروندبوم)، صنایع دستی زنان ترکمن (تیدا)، محصولات زنان بلوچ (چاگرد)، صنایع دستی زنان کرمان (لنا) و "
     "گروه توان‌افزایی زنان (مهرباف)، و دو گروه توانمندسازی شامل بنیاد توسعه کارآفرینی زنان و جوانان و خانه "
     "شتاب‌دهنده صنایع دستی هفت دست، به همراه دو فرد حقیقی در این مسیر همکاری و هم‌افزایی کردند.</p>"),
    ("heading", "چشم‌انداز"),
    ("paragraph",
     "<p>خانه تجارت عادلانه به دنبال آن است که تولیدکنندگان، به‌ویژه از جوامع محلی و گروه‌های حاشیه‌ای، در "
     "محیطی منصفانه و پایدار کار کنند و از حقوق عادلانه برخوردار باشند. در چشم‌انداز ما تجارت ابزاری برای تقویت "
     "عدالت اجتماعی، حفاظت از محیط زیست و گسترش فرصت‌ها برای گروه‌های به حاشیه رانده شده است؛ جهانی که در آن "
     "رعایت حقوق انسان‌ها و حفظ محیط زیست بر سود مادی اولویت داشته باشد.</p>"),
    ("heading", "مأموریت"),
    ("paragraph",
     "<p>خانه تجارت عادلانه ایران مرجع ترویج و اجرای اصول ده‌گانه تجارت عادلانه در ایران خواهد بود. این مجموعه "
     "با ترویج تجارت عادلانه بین مردم و ایجاد همکاری و هم‌افزایی میان اعضای خود، شامل تولیدکنندگان، "
     "توزیع‌کنندگان، فروشندگان و تسهیلگران این حوزه، تلاش می‌کند شرایط کاری مناسب، پرداخت عادلانه و دسترسی به "
     "بازارهای داخلی و بین‌المللی را برای جوامع محلی و گروه‌های حاشیه‌ای فراهم کند و همواره بر اجرای اصول "
     "تجارت عادلانه در سازمان‌های عضو نظارت داشته باشد.</p>"),
    ("heading", "ساختار"),
    ("paragraph",
     "<p>مجمع عمومی اعضا بالاترین مرجع تصمیم‌گیری است و هیئت مدیره، دبیر مجمع و کمیسیون نظارتی مستقل را "
     "برمی‌گزیند. دبیر اجرایی و دبیرخانه کارگروه‌های آموزش و ترویج، توسعه بازار، روابط عمومی، مالی و پایداری، و "
     "مستندسازی و برنامه‌ریزی را هماهنگ می‌کنند. کمیسیون نظارتی مستقل پذیرش اعضا، ممیزی و رسیدگی به شکایات را "
     "بر عهده دارد.</p>"),
)

_ABOUT_EN = stream(
    ("paragraph",
     "<p>The Fair Trade House of Iran is a national network for promoting, supporting and developing the "
     "principles of fair trade in Iran. The idea was put forward in winter 2025 by Haft Dast House and the "
     "Papital group, based on the needs of small businesses for awareness-raising and sales support grounded "
     "in the ten principles of fair trade. Groups whose work or concerns matched these principles were invited "
     "to found the network.</p>"),
    ("paragraph",
     "<p>Seven producer groups (Armoz native products of Minab, Papital jewellery, Parvand Boom native products "
     "of southern Fars, Tida handicrafts by Turkmen women, Chagerd products by Baluch women, Lena handicrafts by "
     "Kerman women and Mehrbaf women's empowerment group), two capacity-building organisations (the Women and "
     "Youth Entrepreneurship Development Foundation and Haft Dast Handicrafts Accelerator) and two individuals "
     "joined forces on this path.</p>"),
    ("heading", "Vision"),
    ("paragraph",
     "<p>We want producers, especially from local communities and marginalised groups, to work in a fair and "
     "sustainable environment and to enjoy fair rights. We see trade as a tool for social justice, environmental "
     "protection and wider opportunity: a world where human rights and the environment come before profit.</p>"),
    ("heading", "Mission"),
    ("paragraph",
     "<p>The Fair Trade House of Iran aims to be the reference for promoting and applying the ten principles of "
     "fair trade in Iran. By promoting fair trade among the public and building cooperation among its members "
     "(producers, distributors, retailers and facilitators), it works to secure good working conditions, fair "
     "pay and access to domestic and international markets for local communities and marginalised groups, and "
     "it monitors how member organisations apply the principles.</p>"),
    ("heading", "Structure"),
    ("paragraph",
     "<p>The General Assembly of members is the highest decision-making body. It elects the Board, the Assembly "
     "Secretary and an independent Supervisory Commission. The Executive Secretary and secretariat coordinate "
     "working groups for education and promotion, market development, public relations, finance and "
     "sustainability, and documentation and planning. The independent Supervisory Commission handles admission "
     "of members, audits and complaints.</p>"),
)

ABOUT = {
    "fa": {
        "title": "درباره ما",
        "slug": "about",
        "intro": "شبکه‌ای ملی برای ترویج، حمایت و توسعه اصول تجارت عادلانه در ایران",
        "body": _ABOUT_FA,
    },
    "en": {
        "title": "About us",
        "slug": "about",
        "intro": "A national network promoting, supporting and developing fair trade in Iran",
        "body": _ABOUT_EN,
    },
}

PRINCIPLES_PAGE = {
    "fa": {
        "title": "اصول ده‌گانه",
        "slug": "principles",
        "intro": "<p>همه اعضای خانه به رعایت این ده اصل، که بر پایه اصول سازمان جهانی تجارت عادلانه (WFTO) است، متعهد می‌شوند و کمیسیون نظارتی بر اجرای آن‌ها نظارت می‌کند.</p>",
    },
    "en": {
        "title": "The ten principles",
        "slug": "principles",
        "intro": "<p>Every member of the House commits to these ten principles, based on those of the World Fair Trade Organization (WFTO). The Supervisory Commission monitors how they are applied.</p>",
    },
}

PRINCIPLES_FA = [
    ("ایجاد فرصت برای تولیدکنندگان محروم", "کاهش فقر از راه تجارت، با اولویت تولیدکنندگان خرد و گروه‌هایی که دسترسی برابر به بازار ندارند."),
    ("شفافیت و پاسخگویی", "مدیریت و روابط تجاری شفاف، و پاسخگویی به همه ذی‌نفعان."),
    ("رویه‌های تجاری منصفانه", "تجارت با توجه به رفاه اجتماعی، اقتصادی و زیست‌محیطی تولیدکنندگان، نه فقط سود."),
    ("پرداخت منصفانه", "قیمت و دستمزدی که با گفت‌وگو تعیین می‌شود و زندگی شرافتمندانه را ممکن می‌کند."),
    ("منع کار کودک و کار اجباری", "پایبندی به حقوق کودک و نبود هیچ‌گونه کار اجباری در تولید."),
    ("عدم تبعیض، برابری جنسیتی و آزادی تشکل", "برابری در استخدام، دستمزد و تصمیم‌گیری، بدون تبعیض جنسیتی، قومی یا معلولیت."),
    ("شرایط کاری ایمن و مناسب", "محیط کار سالم و ایمن و ساعات کاری منطقی."),
    ("ظرفیت‌سازی", "افزایش مهارت‌ها و توانمندی تولیدکنندگان و کارکنان."),
    ("ترویج تجارت عادلانه", "آگاهی‌بخشی درباره اهداف تجارت عادلانه و ضرورت عدالت بیشتر در تجارت."),
    ("احترام به محیط زیست", "استفاده پایدار از منابع، کاهش ضایعات و انرژی، و بسته‌بندی سازگار با طبیعت."),
]

PRINCIPLES_EN = [
    ("Creating opportunities for disadvantaged producers", "Reducing poverty through trade, putting small producers and those without equal market access first."),
    ("Transparency and accountability", "Transparent management and commercial relations, accountable to all stakeholders."),
    ("Fair trading practices", "Trading with concern for producers' social, economic and environmental well-being, not profit alone."),
    ("Fair payment", "Prices and wages agreed through dialogue that allow a dignified living."),
    ("No child labour and no forced labour", "Respect for children's rights and no forced labour anywhere in production."),
    ("Non-discrimination, gender equity and freedom of association", "Equal hiring, pay and decision-making, without discrimination by gender, ethnicity or disability."),
    ("Good working conditions", "A safe and healthy workplace and reasonable working hours."),
    ("Capacity building", "Developing the skills and capabilities of producers and workers."),
    ("Promoting fair trade", "Raising awareness of the aims of fair trade and the need for greater justice in trade."),
    ("Respect for the environment", "Sustainable use of resources, less waste and energy, and eco-friendly packaging."),
]

SITE_SETTINGS = {
    "tagline": "شبکه ملی ترویج تجارت عادلانه",
    "tagline_en": "A national network for fair trade",
    "footer_text": "خانه تجارت عادلانه ایران؛ شبکه‌ای از تولیدکنندگان، نهادها و حامیانی که به اصول ده‌گانه تجارت عادلانه پایبندند.",
    "footer_text_en": "The Fair Trade House of Iran: a network of producers, organisations and supporters committed to the ten principles of fair trade.",
}

# Groups mirror the bodies in the governance document.
SECRETARIAT = "دبیرخانه"
COMMISSION = "کمیسیون نظارتی"
BOARD = "هیئت مدیره"
PR = "روابط عمومی"
MEMBERS_GROUP = "اعضا"
ASSEMBLY_SECRETARY = "دبیر مجمع"  # secretary of the general assembly and deputy; hears appeals (section 8.2)
MARKET = "کارگروه توسعه بازار"  # market development working group: wholesale enquiries, shop orders, settlement
GROUPS = [SECRETARIAT, COMMISSION, BOARD, PR, MEMBERS_GROUP, ASSEMBLY_SECRETARY, MARKET]

# Document collections and who may download their files.
# An empty list means public.
COLLECTIONS = [
    ("اسناد عمومی", []),
    ("اسناد اعضا", [MEMBERS_GROUP, SECRETARIAT, BOARD, COMMISSION]),
    ("اسناد هیئت مدیره", [BOARD, SECRETARIAT, COMMISSION]),
    ("اسناد کمیسیون نظارتی", [COMMISSION]),
    ("تصاویر اعضا", []),  # photos members upload from the member panel
]


# ---- news, documents, contact ----

NEWS_INDEX = {
    "fa": {"title": "اخبار و رویدادها", "slug": "news",
           "intro": "تازه‌ترین خبرها، رویدادها و نوشته‌های خانه تجارت عادلانه ایران و اعضایش."},
    "en": {"title": "News and events", "slug": "news",
           "intro": "The latest news, events and articles from the Fair Trade House of Iran and its members."},
}

FIRST_NEWS = {
    "fa": {
        "title": "وب‌سایت خانه تجارت عادلانه ایران راه‌اندازی شد",
        "slug": "website-launch",
        "kind": "news",
        "intro": "از این پس خبرها، اسناد و فراخوان عضویت خانه را در این سایت منتشر می‌کنیم.",
        "body": stream((
            "paragraph",
            "<p>وب‌سایت خانه تجارت عادلانه ایران راه‌اندازی شد. در این سایت می‌توانید با اصول ده‌گانه تجارت "
            "عادلانه و اعضای خانه آشنا شوید، اسناد عمومی را بخوانید و برای عضویت درخواست دهید.</p>",
        )),
    },
    "en": {
        "title": "The Fair Trade House of Iran website is live",
        "slug": "website-launch",
        "intro": "From now on we will publish the House's news, documents and membership calls here.",
        "body": stream((
            "paragraph",
            "<p>The Fair Trade House of Iran has launched its website. Here you can learn about the ten "
            "principles of fair trade and our members, read our public documents and apply for membership.</p>",
        )),
    },
}

DOCUMENTS_PAGE = {
    "fa": {"title": "اسناد", "slug": "documents",
           "intro": "اساسنامه، آیین‌نامه‌ها، گزارش‌ها و دیگر اسناد خانه تجارت عادلانه ایران."},
    "en": {"title": "Documents", "slug": "documents",
           "intro": "Statutes, regulations, reports and other documents of the Fair Trade House of Iran."},
}

# (collection name, heading fa, heading en, description fa, description en, show to people without access)
DOCUMENT_SECTIONS = [
    ("اسناد عمومی", "اسناد عمومی", "Public documents",
     "اسنادی که همه می‌توانند بخوانند.", "Documents anyone can read.", False),
    ("اسناد اعضا", "ویژه اعضا", "For members",
     "صورت‌جلسه‌ها و اسنادی که فقط اعضای خانه می‌بینند.", "Minutes and documents for members of the House.", True),
    ("اسناد هیئت مدیره", "هیئت مدیره", "Board",
     "اسناد هیئت مدیره.", "Board documents.", False),
    ("اسناد کمیسیون نظارتی", "کمیسیون نظارتی", "Supervisory Commission",
     "اسناد کمیسیون نظارتی.", "Supervisory Commission documents.", False),
]

COMPLAINT_PAGE = {
    "fa": {
        "title": "ثبت شکایت محرمانه",
        "slug": "complaint",
        "intro": "<p>اگر از رفتار یکی از اعضا یا از عملکرد خود خانه شکایتی دارید، آن را این‌جا ثبت کنید. "
                 "طبق سند ارکان، رسیدگی به شکایات با <b>کمیسیون نظارتی</b> است که مستقل از هیئت مدیره کار می‌کند.</p>",
        "privacy_note": "<p>شکایت شما فقط برای اعضای کمیسیون نظارتی قابل مشاهده است؛ نه هیئت مدیره، نه دبیرخانه "
                        "و نه عضوی که از او شکایت کرده‌اید آن را نمی‌بینند.</p>"
                        "<p>می‌توانید بی‌نام شکایت کنید. اگر راه تماسی بگذارید، کمیسیون نتیجه را به شما خبر می‌دهد.</p>",
        "thank_you_text": "<p>شکایت شما ثبت شد و به کمیسیون نظارتی رسید. سپاس از این‌که به بهتر شدن خانه کمک می‌کنید.</p>",
    },
    "en": {
        "title": "Make a confidential complaint",
        "slug": "complaint",
        "intro": "<p>If you have a complaint about one of our members or about the House itself, you can make it here. "
                 "Under our governance document, complaints are handled by the <b>Supervisory Commission</b>, "
                 "which works independently of the Board.</p>",
        "privacy_note": "<p>Only members of the Supervisory Commission can read your complaint. The Board, the "
                        "secretariat and the member you complain about cannot see it.</p>"
                        "<p>You may stay anonymous. If you leave contact details, the commission will tell you the outcome.</p>",
        "thank_you_text": "<p>Your complaint has been received by the Supervisory Commission. Thank you for helping the House improve.</p>",
    },
}

CONTACT_PAGE = {
    "fa": {
        "title": "تماس با ما",
        "slug": "contact",
        "intro": "<p>پرسش، پیشنهاد یا درخواست همکاری دارید؟ پیامتان را بفرستید؛ دبیرخانه پاسخ می‌دهد.</p>",
        "thank_you_text": "<p>سپاس؛ پیام شما به دبیرخانه رسید و به‌زودی پاسخ می‌دهیم.</p>",
        "subject": "پیام تازه از فرم تماس سایت",
    },
    "en": {
        "title": "Contact us",
        "slug": "contact",
        "intro": "<p>A question, a suggestion or an idea for working together? Send us a message and the secretariat will reply.</p>",
        "thank_you_text": "<p>Thank you, your message has reached the secretariat. We will reply soon.</p>",
        "subject": "New message from the website contact form (English)",
    },
}

# (label fa, label en, field type, required)
CONTACT_FIELDS = [
    ("نام", "Name", "singleline", True),
    ("ایمیل", "Email", "email", True),
    ("موضوع", "Subject", "singleline", False),
    ("پیام", "Message", "multiline", True),
]
