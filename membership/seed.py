"""
Starting content for membership: the page (Persian and English), form
questions, e-mail texts, certificate wording and group permissions.
Called from `seed_content`; safe to run again, never overwrites edits.
"""

import json

from django.contrib.auth.models import Group, Permission

from core.models import MembershipSettings

from .email_defaults import DEFAULT_EMAILS
from .models import ApplicationQuestion, EmailTemplate, MembershipPage


def stream(*blocks):
    return json.dumps([{"type": t, "value": v} for t, v in blocks], ensure_ascii=False)


def steps(*items):
    return json.dumps([{"type": "step", "value": {"title": a, "text": b}} for a, b in items], ensure_ascii=False)


PAGE = {
    "fa": {
        "title": "عضویت",
        "slug": "membership",
        "intro": "به شبکه‌ای از تولیدکنندگان، نهادها و حامیانی بپیوندید که به اصول ده‌گانه تجارت عادلانه پایبندند.",
        "body": stream(
            ("cards", {
                "heading": "عضویت در خانه چه می‌دهد؟",
                "cards": [
                    {"title": "تجمیع توان و منابع", "text": "نمایشگاه‌ها، آموزش‌ها و امکانات مشترکی که دسترسی به آن‌ها به‌تنهایی دشوار است."},
                    {"title": "نشان معتبر", "text": "اعضای رسمی می‌توانند از نشان خانه برای معرفی و جلب اعتماد استفاده کنند."},
                    {"title": "بازارهای تازه", "text": "فروش در فروشگاه خانه و اتصال به خریداران آگاه و فرصت‌های صادراتی."},
                    {"title": "شبکه‌سازی و یادگیری", "text": "تبادل تجربه، آموزش و همکاری‌های مشترک میان اعضا."},
                    {"title": "کاهش هزینه و ریسک", "text": "سازوکارهای جمعی برای تبلیغات، آموزش و تأمین مواد اولیه."},
                    {"title": "صدا در تصمیم‌ها", "text": "اعضای رسمی در مجمع عمومی حق رأی دارند و می‌توانند نامزد ارکان شوند."},
                ],
            }),
        ),
        "producer_text": "فرد، کارگاه، تعاونی یا بنگاه کوچکی که خود کالا یا خدمتی تولید می‌کند و فعالیت اصلی آن تولید است؛ با اولویت تولیدکنندگان خرد و گروه‌های محروم از دسترسی برابر به بازار.",
        "institution_text": "شخص حقوقی غیرانتفاعی (سازمان مردم‌نهاد، بنیاد، انجمن یا مرکز علمی) که تجارت محصولات فعالیت اصلی آن نیست، اما از راه آموزش، تأمین مالی، پژوهش یا حمایتگری از تجارت عادلانه پشتیبانی می‌کند.",
        "network_text": "تشکل ملی، منطقه‌ای یا موضوعی متشکل از چند سازمان یا تولیدکننده که هدف آن هماهنگی، نمایندگی و ترویج تجارت عادلانه میان اعضای خود است.",
        "individual_text": "شخص حقیقی که به اصول تجارت عادلانه پایبند است و با دانش، وقت یا منابع مالی خود از آن حمایت می‌کند، بدون آنکه نماینده شخص حقوقی باشد.",
        "fees_note": "<p>مبالغ را مجمع عمومی تعیین می‌کند. هزینه درخواست مستقل از نتیجه و غیرقابل استرداد است.</p>",
        "process_heading": "مراحل پذیرش",
        "process_steps": steps(
            ("درخواست", "فرم عضویت را پر کنید، مدارک را پیوست کنید و هزینه درخواست را بپردازید. کد پیگیری به ایمیل شما فرستاده می‌شود."),
            ("کنترل مدارک", "دبیرخانه ظرف {secretariat_days} روز کامل بودن پرونده را بررسی می‌کند و آن را به کمیسیون نظارتی می‌فرستد."),
            ("ارزیابی", "کمیسیون نظارتی ظرف {commission_days} روز ارزیابی اسنادی را انجام می‌دهد. برای تولیدکنندگان، بازدید میدانی نیز الزامی است."),
            ("رأی کمیسیون", "یکی از سه حالت «پذیرش آزمایشی»، «درخواست اصلاح» یا «رد مستدل»؛ دبیرخانه رأی را به شما ابلاغ می‌کند."),
            ("دوره آزمایشی", "{trial_months} ماه، با دسترسی به آموزش‌ها و خدمات پایه. اعضای آزمایشی حق رأی، نامزدی و استفاده از نشان خانه را ندارند."),
            ("ارزیابی پایانی", "کمیسیون در پایان دوره یکی از سه رأی «تبدیل به عضو رسمی»، «تمدید یک‌باره» یا «عدم پذیرش» را صادر می‌کند."),
            ("ثبت و گواهی", "دبیرخانه عضو رسمی را ثبت و گواهی عضویت صادر می‌کند. اعتبار گواهی را هر کسی در همین سایت می‌تواند استعلام کند."),
        ),
        "conditions": (
            "<ol><li>فعالیت واقعی و مستند در گروه مربوط.</li>"
            "<li>امضای تعهدنامه رعایت اصول ده‌گانه تجارت عادلانه.</li>"
            "<li>پذیرش کتبی بازرسی‌های دوره‌ای و سرزده، برای تولیدکنندگان.</li>"
            "<li>ارائه اطلاعات شفاف درباره نیروی کار، دستمزد و زنجیره تأمین، برای تولیدکنندگان.</li>"
            "<li>پرداخت هزینه درخواست عضویت و حق عضویت سالانه.</li></ol>"
        ),
        "form_intro": "<p>لطفاً فرم را با دقت پر کنید. پرسش‌های ستاره‌دار اجباری‌اند. پس از ارسال، کد پیگیری به ایمیل شما فرستاده می‌شود.</p>",
        "payment_text": "<p>هزینه درخواست را به حساب زیر واریز کنید و تصویر رسید را پیوست کنید.</p>",
        "commitment_text": (
            "<p>با ارسال این درخواست متعهد می‌شوم اصول ده‌گانه تجارت عادلانه را رعایت کنم: ایجاد فرصت برای "
            "تولیدکنندگان محروم، شفافیت و پاسخگویی، رویه‌های تجاری منصفانه، پرداخت منصفانه، منع کار کودک و "
            "کار اجباری، عدم تبعیض و برابری جنسیتی و آزادی تشکل، شرایط کاری ایمن و مناسب، ظرفیت‌سازی، ترویج "
            "تجارت عادلانه و احترام به محیط زیست. می‌دانم که کمیسیون نظارتی بر اجرای این اصول نظارت می‌کند.</p>"
        ),
        "inspection_text": "بازرسی‌های دوره‌ای و سرزده خانه را می‌پذیرم و اطلاعات نیروی کار، دستمزد و زنجیره تأمین را شفاف در اختیار کمیسیون می‌گذارم.",
        "privacy_text": "مدارک شما محرمانه است و فقط دبیرخانه و کمیسیون نظارتی آن‌ها را می‌بینند.",
        "success_text": "<p>سپاس از اعتماد شما. هر مرحله از بررسی پرونده با ایمیل به شما خبر داده می‌شود و وضعیت را هر زمان در صفحه پیگیری می‌بینید.</p>",
        "closed_text": "<p>در حال حاضر درخواست عضویت تازه پذیرفته نمی‌شود. برای اطلاع از زمان بازگشایی با دبیرخانه در تماس باشید.</p>",
        "track_intro": "<p>کد پیگیری و ایمیلی را که در فرم نوشتید وارد کنید تا وضعیت پرونده را ببینید.</p>",
        "certificate_intro": "<p>شماره گواهی عضویت را وارد کنید تا ببینید معتبر است یا نه.</p>",
    },
    "en": {
        "title": "Membership",
        "slug": "membership",
        "intro": "Join a network of producers, organisations and supporters committed to the ten principles of fair trade.",
        "body": stream(
            ("cards", {
                "heading": "What membership offers",
                "cards": [
                    {"title": "Pooled strength", "text": "Shared exhibitions, training and resources that are hard to reach alone."},
                    {"title": "A trusted mark", "text": "Full members may use the House's mark to build visibility and trust."},
                    {"title": "New markets", "text": "Sales through the House's shop, conscious buyers and export opportunities."},
                    {"title": "Network and learning", "text": "Exchange of experience, training and joint projects among members."},
                    {"title": "Lower costs and risks", "text": "Shared mechanisms for advertising, training and sourcing raw materials."},
                    {"title": "A voice in decisions", "text": "Full members vote in the General Assembly and can stand for its bodies."},
                ],
            }),
        ),
        "producer_text": "An individual, workshop, cooperative or small business that makes its own goods or services as its main activity; small producers and groups without equal market access come first.",
        "institution_text": "A non-profit legal entity (NGO, foundation, association or research centre) whose main activity is not trading products, but which supports fair trade through training, funding, research or advocacy.",
        "network_text": "A national, regional or thematic body of several organisations or producers that coordinates, represents and promotes fair trade among its members.",
        "individual_text": "A person committed to the principles of fair trade who supports it with knowledge, time or money, without representing a legal entity.",
        "fees_note": "<p>Amounts are set by the General Assembly. The application fee is non-refundable, whatever the outcome.</p>",
        "process_heading": "How admission works",
        "process_steps": steps(
            ("Application", "Fill in the form, attach your documents and pay the application fee. A tracking code is e-mailed to you."),
            ("Document check", "Within {secretariat_days} days the secretariat checks that the file is complete and sends it to the Supervisory Commission."),
            ("Evaluation", "Within {commission_days} days the commission evaluates the documents. For producers a field visit is also required."),
            ("Commission decision", "Trial acceptance, a request for changes, or a reasoned rejection; the secretariat informs you."),
            ("Trial period", "{trial_months} months with access to training and basic services. Trial members cannot vote, stand for election or use the House's mark."),
            ("Final evaluation", "At the end of the trial the commission decides: full membership, a one-off extension, or not accepted."),
            ("Registration and certificate", "The secretariat registers the full member and issues a membership certificate, which anyone can check on this site."),
        ),
        "conditions": (
            "<ol><li>Real, documented activity in the relevant group.</li>"
            "<li>Signing the commitment to the ten principles of fair trade.</li>"
            "<li>Written acceptance of periodic and unannounced inspections (producers).</li>"
            "<li>Transparent information on workforce, wages and supply chain (producers).</li>"
            "<li>Payment of the application fee and the annual membership fee.</li></ol>"
        ),
        "form_intro": "<p>Please fill in the form carefully. Questions marked with a star are required. After sending, a tracking code is e-mailed to you.</p>",
        "payment_text": "<p>Pay the application fee to the account below and attach a picture of the receipt.</p>",
        "commitment_text": (
            "<p>By sending this application I commit to the ten principles of fair trade: opportunities for "
            "disadvantaged producers, transparency and accountability, fair trading practices, fair payment, no "
            "child or forced labour, non-discrimination, gender equity and freedom of association, good working "
            "conditions, capacity building, promoting fair trade, and respect for the environment. I understand "
            "that the Supervisory Commission monitors how these principles are applied.</p>"
        ),
        "inspection_text": "I accept periodic and unannounced inspections by the House and will share clear information on our workforce, wages and supply chain with the commission.",
        "privacy_text": "Your documents are confidential and are seen only by the secretariat and the Supervisory Commission.",
        "success_text": "<p>Thank you. You will receive an e-mail at each step, and you can check the status at any time on the tracking page.</p>",
        "closed_text": "<p>We are not accepting new applications at the moment. Please contact the secretariat to find out when they reopen.</p>",
        "track_intro": "<p>Enter your tracking code and the e-mail you used in the form to see the status of your file.</p>",
        "certificate_intro": "<p>Enter a membership certificate number to check whether it is valid.</p>",
    },
}

# (label, label_en, help, help_en, type, required, types, choices, choices_en)
P, I, N, V = "producer", "institution", "network", "individual"
QUESTIONS = [
    ("شرح فعالیت و محصولات یا خدمات", "Describe your work and your products or services",
     "چه می‌سازید، از کی، و برای چه کسانی", "What you make, since when, and for whom", "textarea", True, [P], "", ""),
    ("شکل فعالیت", "Type of organisation", "", "", "select", True, [P],
     "فرد\nکارگاه\nتعاونی\nشرکت\nگروه غیررسمی", "Individual\nWorkshop\nCooperative\nCompany\nInformal group"),
    ("سال شروع فعالیت", "Year you started", "", "", "text", True, [P, I, N], "", ""),
    ("تعداد افراد شاغل و تعداد زنان در میان آن‌ها", "Number of people working, and how many are women",
     "", "", "text", True, [P], "", ""),
    ("شیوه تعیین دستمزد و پرداخت به کارکنان یا تولیدکنندگان", "How wages and payments to workers or producers are set",
     "شفافیت درباره دستمزد از شرایط پذیرش تولیدکنندگان است", "Transparency on wages is a condition for producers",
     "textarea", True, [P], "", ""),
    ("زنجیره تأمین: مواد اولیه از کجا و چگونه تأمین می‌شود؟", "Supply chain: where and how do you source raw materials?",
     "", "", "textarea", True, [P], "", ""),
    ("نمونه کار یا کاتالوگ محصولات", "Product samples or catalogue", "عکس یا PDF", "Photos or a PDF",
     "file", False, [P], "", ""),
    ("مجوز یا مدرک ثبت (اگر دارید)", "Licence or registration document (if any)", "", "", "file", False, [P], "", ""),
    ("شماره و محل ثبت", "Registration number and place", "", "", "text", True, [I, N], "", ""),
    ("فعالیت‌های شما در حمایت از تجارت عادلانه", "How you support fair trade",
     "آموزش، تأمین مالی، پژوهش، حمایتگری و …", "Training, funding, research, advocacy …", "textarea", True, [I], "", ""),
    ("اعضای شبکه", "Members of the network", "نام سازمان‌ها یا تولیدکنندگان عضو", "Names of member organisations or producers",
     "textarea", True, [N], "", ""),
    ("هدف و فعالیت‌های شبکه", "Aims and activities of the network", "", "", "textarea", True, [N], "", ""),
    ("اساسنامه یا مدرک ثبت", "Statutes or registration document", "", "", "file", True, [I, N], "", ""),
    ("حرفه یا زمینه فعالیت", "Profession or field", "", "", "text", True, [V], "", ""),
    ("چگونه از تجارت عادلانه حمایت می‌کنید یا می‌خواهید حمایت کنید؟", "How do you (or will you) support fair trade?",
     "با دانش، وقت یا منابع مالی", "With knowledge, time or money", "textarea", True, [V], "", ""),
    ("مستندات فعالیت (لینک یا توضیح)", "Evidence of your activity (links or description)",
     "فعالیت واقعی و مستند از شرایط پذیرش است", "Real, documented activity is a condition of membership",
     "textarea", False, [P, I, N, V], "", ""),
]

CERTIFICATE_TEXT_FA = (
    "بدین‌وسیله گواهی می‌شود {name} پس از طی مراحل پذیرش و دوره آزمایشی، در گروه «{type}» به عضویت رسمی "
    "خانه تجارت عادلانه ایران درآمده و به رعایت اصول ده‌گانه تجارت عادلانه متعهد است."
)
CERTIFICATE_TEXT_EN = (
    "This is to certify that {name}, having completed the admission process and trial period, is a full member "
    "of the Fair Trade House of Iran in the group \"{type}\" and is committed to the ten principles of fair trade."
)


def ensure_membership(home_fa, home_en, stdout=None, fresh=None):
    page_fa = MembershipPage.objects.filter(locale=home_fa.locale).first()
    if page_fa is None:
        page_fa = MembershipPage(show_in_menus=True, **PAGE["fa"])
        fresh(home_fa).add_child(instance=page_fa)
        page_fa.save_revision().publish()
        stdout and stdout.write("Created membership page (fa)")
    page_fa = MembershipPage.objects.get(pk=page_fa.pk)
    if page_fa.get_translation_or_none(home_en.locale) is None:
        page_en = page_fa.copy_for_translation(home_en.locale).specific
        for field, value in PAGE["en"].items():
            setattr(page_en, field, value)
        page_en.save_revision().publish()
        stdout and stdout.write("Created membership page (en)")

    if not ApplicationQuestion.objects.exists():
        for order, (label, label_en, help_fa, help_en, ftype, required, types, choices, choices_en) in enumerate(QUESTIONS):
            ApplicationQuestion.objects.create(
                label=label, label_en=label_en, help_text=help_fa, help_text_en=help_en, field_type=ftype,
                required=required, choices=choices, choices_en=choices_en, sort_order=(order + 1) * 10,
                **{f"for_{t}": True for t in types},
            )

    for event, (subject, body, subject_en, body_en) in DEFAULT_EMAILS.items():
        EmailTemplate.objects.get_or_create(
            event=event, defaults={"subject": subject, "body": body, "subject_en": subject_en, "body_en": body_en},
        )

    ms = MembershipSettings.load()
    if not ms.certificate_text:
        ms.certificate_text = CERTIFICATE_TEXT_FA
        ms.certificate_text_en = ms.certificate_text_en or CERTIFICATE_TEXT_EN
        ms.save()


def ensure_permissions(secretariat, commission, board):
    """Give the governance bodies their rights on membership files."""

    def perms(model, *codenames):
        return list(Permission.objects.filter(content_type__app_label="membership",
                                              content_type__model=model, codename__in=codenames))

    view = perms("membershipapplication", "view_membershipapplication")
    snippets = (perms("applicationquestion", "add_applicationquestion", "change_applicationquestion",
                      "delete_applicationquestion", "view_applicationquestion")
                + perms("emailtemplate", "add_emailtemplate", "change_emailtemplate", "view_emailtemplate")
                + perms("certificate", "change_certificate", "view_certificate"))
    dues = list(Permission.objects.filter(content_type__app_label="standing", codename__in=[
        "view_dues", "change_dues", "view_duespayment", "view_decision"]))
    for group, extra in (
        (secretariat, perms("membershipapplication", "secretariat_actions") + snippets + dues),
        (commission, perms("membershipapplication", "commission_actions") + perms("certificate", "view_certificate")),
        (board, perms("certificate", "view_certificate")),
    ):
        if isinstance(group, Group):
            group.permissions.add(*view, *extra)
