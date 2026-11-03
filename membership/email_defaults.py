"""
Starting texts for membership e-mails. seed_content copies them into the
EmailTemplate snippets, where the secretariat edits them; they are also the
fallback when a template has been deleted.
"""

SIGN_FA = "\n\nبا احترام،\nدبیرخانه {site_name}"
SIGN_EN = "\n\nKind regards,\nSecretariat, {site_name}"

DEFAULT_EMAILS = {
    "received": (
        "درخواست عضویت شما دریافت شد ({code})",
        "{name} گرامی،\n\nدرخواست عضویت شما در گروه «{type}» دریافت شد. کد پیگیری شما {code} است؛ "
        "آن را نگه دارید.\n\nدبیرخانه تا {deadline} کامل بودن پرونده را بررسی می‌کند. وضعیت پرونده را "
        "هر زمان با کد پیگیری و ایمیل خود در این نشانی ببینید:\n{track_url}" + SIGN_FA,
        "We received your membership application ({code})",
        "Dear {name},\n\nWe received your application to join as \"{type}\". Your tracking code is {code}; "
        "please keep it.\n\nThe secretariat will check your file by {deadline}. You can follow its status "
        "at any time with your tracking code and e-mail here:\n{track_url}" + SIGN_EN,
    ),
    "staff_new": (
        "درخواست عضویت تازه: {name} ({type})",
        "درخواست عضویت تازه‌ای ثبت شد.\n\nمتقاضی: {name}\nنوع عضویت: {type}\nکد پیگیری: {code}\n"
        "مهلت کنترل مدارک: {deadline}\n\nبررسی پرونده:\n{admin_url}",
        "", "",
    ),
    "staff_resubmitted": (
        "متقاضی مدارک تکمیلی فرستاد: {name} ({code})",
        "متقاضی {name} (کد {code}) به درخواست شما پاسخ داد و مدارک یا اصلاحات را فرستاد.\n\n"
        "وضعیت فعلی: {status}\nمهلت: {deadline}\n\nبررسی پرونده:\n{admin_url}",
        "", "",
    ),
    "commission_new": (
        "پرونده عضویت برای ارزیابی: {name} ({type})",
        "دبیرخانه پرونده زیر را کامل اعلام کرد و برای ارزیابی کمیسیون نظارتی فرستاد.\n\n"
        "متقاضی: {name}\nنوع عضویت: {type}\nکد پیگیری: {code}\nمهلت ارزیابی: {deadline}\n\n"
        "بررسی پرونده:\n{admin_url}",
        "", "",
    ),
    "staff_reminder": (
        "یادآوری مهلت پرونده‌های عضویت",
        "این پرونده‌های عضویت به پایان مهلت نزدیک‌اند یا از مهلت گذشته‌اند:\n\n{list}\n\n"
        "فهرست کامل:\n{admin_url}",
        "", "",
    ),
    "status_incomplete": (
        "پرونده عضویت شما کامل نیست ({code})",
        "{name} گرامی،\n\nدبیرخانه پرونده شما را بررسی کرد و این موارد لازم است:\n\n{message}\n\n"
        "لطفاً از صفحه پیگیری، با کد {code}، مدارک را بفرستید:\n{track_url}" + SIGN_FA,
        "Your membership file is incomplete ({code})",
        "Dear {name},\n\nThe secretariat checked your file and needs the following:\n\n{message}\n\n"
        "Please send the documents from the tracking page with your code {code}:\n{track_url}" + SIGN_EN,
    ),
    "status_commission": (
        "پرونده شما به کمیسیون نظارتی رفت ({code})",
        "{name} گرامی،\n\nپرونده شما کامل است و برای ارزیابی به کمیسیون نظارتی فرستاده شد. کمیسیون تا "
        "{deadline} ارزیابی را انجام می‌دهد. برای تولیدکنندگان، بازدید میدانی هم انجام می‌شود و برای "
        "هماهنگی با شما تماس می‌گیریم.\n{message}" + SIGN_FA,
        "Your file has gone to the Supervisory Commission ({code})",
        "Dear {name},\n\nYour file is complete and has been sent to the Supervisory Commission, which will "
        "evaluate it by {deadline}. For producers a field visit is part of the evaluation; we will contact "
        "you to arrange it.\n{message}" + SIGN_EN,
    ),
    "status_fix_requested": (
        "کمیسیون نظارتی اصلاحاتی درخواست کرد ({code})",
        "{name} گرامی،\n\nکمیسیون نظارتی پرونده شما را بررسی کرد و این اصلاحات را درخواست کرده است:\n\n"
        "{message}\n\nپس از انجام، از صفحه پیگیری پاسخ و مدارک خود را بفرستید:\n{track_url}" + SIGN_FA,
        "The Supervisory Commission requested changes ({code})",
        "Dear {name},\n\nThe Supervisory Commission reviewed your file and asks for these changes:\n\n"
        "{message}\n\nWhen they are done, send your reply and documents from the tracking page:\n{track_url}"
        + SIGN_EN,
    ),
    "status_rejected": (
        "نتیجه درخواست عضویت ({code})",
        "{name} گرامی،\n\nسپاس از علاقه شما به خانه. کمیسیون نظارتی پس از بررسی، درخواست عضویت شما را "
        "به این دلیل نپذیرفت:\n\n{message}\n\nاگر به این رأی اعتراض دارید، می‌توانید ظرف ۳۰ روز از این "
        "ابلاغ اعتراض کتبی خود را به دبیر مجمع بفرستید." + SIGN_FA,
        "Result of your membership application ({code})",
        "Dear {name},\n\nThank you for your interest in the House. After review, the Supervisory Commission "
        "did not accept your application, for this reason:\n\n{message}\n\nIf you disagree, you can send a "
        "written appeal to the Assembly Secretary within 30 days of this notice." + SIGN_EN,
    ),
    "status_trial": (
        "خوش آمدید: پذیرش آزمایشی در خانه تجارت عادلانه ({code})",
        "{name} گرامی،\n\nکمیسیون نظارتی عضویت آزمایشی شما را پذیرفت. دوره آزمایشی تا {deadline} ادامه دارد "
        "و در این مدت به آموزش‌ها و خدمات پایه خانه دسترسی دارید. اعضای آزمایشی حق رأی، نامزدی و استفاده از "
        "نشان خانه را ندارند. در پایان دوره، کمیسیون ارزیابی پایانی را انجام می‌دهد.\n{message}" + SIGN_FA,
        "Welcome: trial membership of the Fair Trade House ({code})",
        "Dear {name},\n\nThe Supervisory Commission accepted you as a trial member. The trial lasts until "
        "{deadline}; during it you can join the House's training and basic services. Trial members cannot "
        "vote, stand for election or use the House's mark. At the end of the trial the commission makes a "
        "final evaluation.\n{message}" + SIGN_EN,
    ),
    "status_trial_extended": (
        "دوره آزمایشی شما تمدید شد ({code})",
        "{name} گرامی،\n\nکمیسیون نظارتی دوره آزمایشی شما را یک بار تمدید کرد. دوره تازه تا {deadline} "
        "ادامه دارد.\n{message}" + SIGN_FA,
        "Your trial period has been extended ({code})",
        "Dear {name},\n\nThe Supervisory Commission extended your trial period once. It now ends on "
        "{deadline}.\n{message}" + SIGN_EN,
    ),
    "status_not_accepted": (
        "نتیجه ارزیابی پایانی دوره آزمایشی ({code})",
        "{name} گرامی،\n\nکمیسیون نظارتی در ارزیابی پایانی، عضویت رسمی شما را نپذیرفت:\n\n{message}\n\n"
        "اگر به این رأی اعتراض دارید، می‌توانید ظرف ۳۰ روز اعتراض کتبی خود را به دبیر مجمع بفرستید." + SIGN_FA,
        "Result of your trial period ({code})",
        "Dear {name},\n\nIn its final evaluation the Supervisory Commission did not accept you as a full "
        "member:\n\n{message}\n\nYou can send a written appeal to the Assembly Secretary within 30 days."
        + SIGN_EN,
    ),
    "status_approved": (
        "تبریک: عضویت رسمی شما تأیید شد ({code})",
        "{name} گرامی،\n\nکمیسیون نظارتی عضویت رسمی شما را تأیید کرد. دبیرخانه به‌زودی عضویت شما را ثبت و "
        "گواهی عضویت را صادر می‌کند.\n{message}" + SIGN_FA,
        "Congratulations: your full membership is approved ({code})",
        "Dear {name},\n\nThe Supervisory Commission approved your full membership. The secretariat will "
        "register you and issue your membership certificate shortly.\n{message}" + SIGN_EN,
    ),
    "status_member": (
        "گواهی عضویت شما صادر شد ({certificate_number})",
        "{name} گرامی،\n\nعضویت رسمی شما ثبت شد و گواهی عضویت به شماره {certificate_number} صادر شد. "
        "هر کس می‌تواند اعتبار این گواهی را در این نشانی بررسی کند:\n{certificate_url}\n{message}" + SIGN_FA,
        "Your membership certificate has been issued ({certificate_number})",
        "Dear {name},\n\nYour full membership is registered and certificate number {certificate_number} has "
        "been issued. Anyone can check it here:\n{certificate_url}\n{message}" + SIGN_EN,
    ),
    "status_withdrawn": (
        "پرونده عضویت شما بایگانی شد ({code})",
        "{name} گرامی،\n\nپرونده درخواست عضویت شما بایگانی شد:\n\n{message}\n\nبرای درخواست دوباره، "
        "فرم عضویت را از نو پر کنید." + SIGN_FA,
        "Your membership file has been archived ({code})",
        "Dear {name},\n\nYour membership application has been archived:\n\n{message}\n\nTo apply again, "
        "please fill in the form anew." + SIGN_EN,
    ),
    "panel_invite": (
        "حساب پنل اعضای شما ساخته شد",
        "{name} گرامی،\n\nبرای شما در پنل اعضای سایت {site_name} حساب کاربری ساخته شد. از این پنل می‌توانید "
        "معرفی مجموعه و محصولات خود را در سایت به‌روز کنید.\n\nنام کاربری: {username}\n\n"
        "برای ساختن رمز عبور این پیوند را باز کنید (پیوند تا چند روز معتبر است):\n{set_password_url}\n\n"
        "پس از آن از این نشانی وارد شوید:\n{panel_url}" + SIGN_FA,
        "Your member panel account is ready",
        "Dear {name},\n\nAn account has been created for you in the member panel of {site_name}. There you "
        "can keep your profile and products on the website up to date.\n\nUsername: {username}\n\n"
        "Open this link to choose your password (it is valid for a few days):\n{set_password_url}\n\n"
        "Then sign in here:\n{panel_url}" + SIGN_EN,
    ),
    "panel_product_review": (
        "محصول تازه در انتظار بررسی: {product} ({member})",
        "عضو «{member}» از پنل اعضا محصول تازه‌ای ثبت کرد که پیش از نمایش در سایت بررسی شما را لازم دارد.\n\n"
        "محصول: {product}\n\nبررسی و انتشار:\n{admin_url}\n\n"
        "برای انتشار، تیک «در انتظار بررسی» را بردارید.",
        "", "",
    ),
    # ---- annual dues ----
    "dues_issued": (
        "حق عضویت سالانه {year}",
        "{name} گرامی،\n\nحق عضویت سالانه سال {year} شما {amount} است. لطفاً تا {due_date} آن را به حساب زیر "
        "واریز کنید و تصویر رسید را در پنل اعضا بفرستید:\n\n{bank}\n\n{panel_url}" + SIGN_FA,
        "Annual membership fee {year}",
        "Dear {name},\n\nYour annual membership fee for {year} is {amount}. Please pay it into the account "
        "below by {due_date} and upload the receipt in the member panel:\n\n{bank}\n\n{panel_url}" + SIGN_EN,
    ),
    "dues_reminder": (
        "یادآوری: مهلت پرداخت حق عضویت {year}",
        "{name} گرامی،\n\nیادآوری می‌کنیم که مهلت پرداخت حق عضویت سال {year} ({amount}) تا {due_date} است. "
        "اگر پرداخت کرده‌اید، رسید را در پنل اعضا بفرستید:\n{panel_url}\n\n{bank}" + SIGN_FA,
        "Reminder: membership fee {year} is due",
        "Dear {name},\n\nA reminder that your membership fee for {year} ({amount}) is due by {due_date}. "
        "If you have paid, please upload the receipt in the member panel:\n{panel_url}\n\n{bank}" + SIGN_EN,
    ),
    "dues_warning": (
        "اخطار کتبی: حق عضویت {year} پرداخت نشده است",
        "{name} گرامی،\n\nمهلت پرداخت حق عضویت سال {year} ({amount}) در {due_date} به پایان رسید و پرداختی "
        "ثبت نشده است. این ایمیل اخطار کتبی موضوع بند ۱.۷ سند ارکان است.\n\nاگر تا {suspend_date} حق عضویت "
        "پرداخت نشود، عضویت شما تعلیق می‌شود. عضو تعلیق‌شده حق رأی، استفاده از نشان و خدمات خانه را ندارد.\n\n"
        "{message}\n\nپرداخت و ارسال رسید:\n{panel_url}\n\n{bank}\n\nاگر به این اخطار اعتراض دارید، تا {appeal_until} "
        "می‌توانید اعتراض کتبی خود را به دبیر مجمع عمومی بدهید." + SIGN_FA,
        "Written warning: membership fee {year} not paid",
        "Dear {name},\n\nThe deadline for your membership fee for {year} ({amount}) was {due_date} and we have "
        "not received a payment. This e-mail is the written warning under section 1.7 of the governance "
        "document.\n\nIf the fee is not paid by {suspend_date}, your membership will be suspended. A suspended "
        "member cannot vote, use the House's mark or use its services.\n\n{message}\n\nPay and upload the "
        "receipt here:\n{panel_url}\n\n{bank}\n\nIf you disagree with this warning, you may send a written "
        "appeal to the Secretary of the General Assembly by {appeal_until}." + SIGN_EN,
    ),
    "dues_receipt_staff": (
        "رسید تازه حق عضویت: {member} ({year})",
        "عضو «{member}» رسید حق عضویت سال {year} ({amount}) را از پنل اعضا فرستاد.\n\n{message}\n\n"
        "بررسی و تأیید:\n{admin_url}",
        "", "",
    ),
    "dues_confirmed": (
        "پرداخت حق عضویت {year} تأیید شد",
        "{name} گرامی،\n\nپرداخت حق عضویت سال {year} ({amount}) شما تأیید شد. سپاس از همراهی شما.\n\n{message}"
        + SIGN_FA,
        "Membership fee {year} received",
        "Dear {name},\n\nWe have confirmed your membership fee for {year} ({amount}). Thank you.\n\n{message}"
        + SIGN_EN,
    ),
    "dues_rejected": (
        "رسید حق عضویت {year} پذیرفته نشد",
        "{name} گرامی،\n\nرسیدی که برای حق عضویت سال {year} فرستادید پذیرفته نشد:\n\n{message}\n\n"
        "لطفاً رسید درست را تا {due_date} در پنل اعضا بفرستید:\n{panel_url}" + SIGN_FA,
        "Membership fee receipt {year} not accepted",
        "Dear {name},\n\nThe receipt you sent for your membership fee for {year} was not accepted:\n\n"
        "{message}\n\nPlease upload the right receipt by {due_date} in the member panel:\n{panel_url}" + SIGN_EN,
    ),
    # ---- standing (sections 1.7, 1.8, 7 and 8.2) ----
    "standing_notice": (
        "تذکر کتبی خانه تجارت عادلانه",
        "{name} گرامی،\n\nاین ایمیل تذکر کتبی خانه به شما است.\n\nموضوع: {reason}\n\n{message}\n\n"
        "اگر اعتراضی دارید، تا {appeal_until} می‌توانید آن را کتبی به دبیر مجمع عمومی بدهید." + SIGN_FA,
        "Written notice from the Fair Trade House",
        "Dear {name},\n\nThis e-mail is a written notice from the House.\n\nSubject: {reason}\n\n{message}"
        + SIGN_EN,
    ),
    "standing_warning": (
        "اخطار کتبی خانه تجارت عادلانه",
        "{name} گرامی،\n\nاین ایمیل اخطار کتبی خانه به شما است.\n\nموضوع: {reason}\n\n{message}\n\n"
        "اگر به این اخطار اعتراض دارید، تا {appeal_until} می‌توانید اعتراض کتبی خود را به دبیر مجمع عمومی بدهید."
        + SIGN_FA,
        "Written warning from the Fair Trade House",
        "Dear {name},\n\nThis e-mail is a written warning from the House.\n\nSubject: {reason}\n\n{message}\n\n"
        "If you disagree, you may send a written appeal to the Secretary of the General Assembly by {appeal_until}."
        + SIGN_EN,
    ),
    "standing_suspend": (
        "تعلیق عضویت شما",
        "{name} گرامی،\n\nعضویت شما در خانه تا {until} تعلیق شد.\n\nدلیل: {reason}\n{message}\n\n"
        "طبق بند ۱.۷ سند ارکان، عضو تعلیق‌شده حق رأی، استفاده از نشان و خدمات خانه را ندارد. تعلیق حداکثر "
        "شش ماه است و پس از آن به رفع تعلیق یا لغو عضویت می‌انجامد.\n\nاگر به این رأی اعتراض دارید، تا "
        "{appeal_until} می‌توانید اعتراض کتبی خود را به دبیر مجمع عمومی بدهید. اعتراض، اجرای تعلیق را متوقف "
        "نمی‌کند.\n\n{panel_url}" + SIGN_FA,
        "Your membership has been suspended",
        "Dear {name},\n\nYour membership of the House is suspended until {until}.\n\nReason: {reason}\n"
        "{message}\n\nUnder section 1.7 of the governance document, a suspended member cannot vote, use the "
        "House's mark or use its services. A suspension lasts at most six months and then ends with the "
        "suspension being lifted or the membership cancelled.\n\nIf you disagree, you may send a written appeal "
        "to the Secretary of the General Assembly by {appeal_until}. An appeal does not pause the suspension."
        "\n\n{panel_url}" + SIGN_EN,
    ),
    "standing_lift": (
        "رفع تعلیق عضویت",
        "{name} گرامی،\n\nتعلیق عضویت شما رفع شد و از امروز دوباره از همه حقوق عضویت برخوردارید.\n\n"
        "{message}" + SIGN_FA,
        "Your suspension has been lifted",
        "Dear {name},\n\nThe suspension of your membership has been lifted; from today you have all the rights "
        "of membership again.\n\n{message}" + SIGN_EN,
    ),
    "standing_cancel": (
        "لغو عضویت",
        "{name} گرامی،\n\nعضویت شما در خانه لغو شد.\n\nدلیل: {reason}\n{message}\n\n"
        "اگر به این رأی اعتراض دارید، تا {appeal_until} می‌توانید اعتراض کتبی خود را به دبیر مجمع عمومی بدهید؛ "
        "تا صدور رأی اعتراض، عضویت شما در وضعیت تعلیق می‌ماند.\n\nدرخواست دوباره عضویت از {reapply_after} ممکن "
        "است." + SIGN_FA,
        "Your membership has been cancelled",
        "Dear {name},\n\nYour membership of the House has been cancelled.\n\nReason: {reason}\n{message}\n\n"
        "If you disagree, you may send a written appeal to the Secretary of the General Assembly by "
        "{appeal_until}.\n\nYou may apply for membership again from {reapply_after}." + SIGN_EN,
    ),
    "standing_reinstate": (
        "بازگشت عضویت",
        "{name} گرامی،\n\nرأی لغو عضویت شما در رسیدگی به اعتراض نقض شد و عضویت شما برقرار است.\n\n{message}"
        + SIGN_FA,
        "Your membership has been reinstated",
        "Dear {name},\n\nThe decision to cancel your membership was overturned on appeal and your membership "
        "continues.\n\n{message}" + SIGN_EN,
    ),
    "standing_digest": (
        "گزارش روزانه حق عضویت و وضعیت اعضا",
        "این موارد به اقدام شما نیاز دارند:\n\n{list}\n\nفهرست کامل:\n{admin_url}",
        "", "",
    ),
}
