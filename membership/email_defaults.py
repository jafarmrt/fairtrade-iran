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
}
