"""SMS texts for the membership workflow (edited later in the admin: پیامک > متن‌های پیامک)."""

from sms.registry import register

S = "\n{site_name}"
S_EN = "\nFair Trade House of Iran"

register("membership_received", "عضویت، به متقاضی: درخواست دریافت شد",
         "{name} گرامی، درخواست عضویت شما با کد پیگیری {code} دریافت شد." + S,
         "Dear {name}, we received your membership application. Tracking code: {code}" + S_EN)
register("membership_status_incomplete", "عضویت، به متقاضی: نقص مدارک",
         "{name} گرامی، پرونده عضویت شما ({code}) کامل نیست. جزئیات به ایمیل شما فرستاده شد.\n{track_url}" + S,
         "Dear {name}, your membership file ({code}) is incomplete. Details were e-mailed to you.\n{track_url}" + S_EN)
register("membership_status_commission", "عضویت، به متقاضی: ارسال به کمیسیون",
         "{name} گرامی، پرونده شما ({code}) کامل است و برای ارزیابی به کمیسیون نظارتی رفت." + S,
         "Dear {name}, your file ({code}) is complete and has gone to the Supervisory Commission." + S_EN)
register("membership_status_fix_requested", "عضویت، به متقاضی: درخواست اصلاح",
         "{name} گرامی، کمیسیون برای پرونده {code} اصلاحاتی خواسته است. جزئیات در ایمیل شماست.\n{track_url}" + S,
         "Dear {name}, the Commission asked for changes to file {code}. Details are in your e-mail.\n{track_url}" + S_EN)
register("membership_status_rejected", "عضویت، به متقاضی: رد مستدل",
         "{name} گرامی، نتیجه بررسی درخواست عضویت شما ({code}) به ایمیل‌تان فرستاده شد." + S,
         "Dear {name}, the result of your membership application ({code}) was e-mailed to you." + S_EN)
register("membership_status_trial", "عضویت، به متقاضی: پذیرش آزمایشی",
         "{name} گرامی، تبریک! عضویت آزمایشی شما ({code}) پذیرفته شد. جزئیات در ایمیل شماست." + S,
         "Dear {name}, congratulations! You were accepted as a trial member ({code}). Details are in your e-mail." + S_EN)
register("membership_status_trial_extended", "عضویت، به متقاضی: تمدید دوره آزمایشی",
         "{name} گرامی، دوره آزمایشی عضویت شما ({code}) تا {deadline} تمدید شد." + S,
         "Dear {name}, your trial membership ({code}) was extended until {deadline}." + S_EN)
register("membership_status_not_accepted", "عضویت، به متقاضی: عدم پذیرش پس از دوره آزمایشی",
         "{name} گرامی، نتیجه دوره آزمایشی عضویت شما ({code}) به ایمیل‌تان فرستاده شد." + S,
         "Dear {name}, the outcome of your trial membership ({code}) was e-mailed to you." + S_EN)
register("membership_status_approved", "عضویت، به متقاضی: تأیید عضویت رسمی",
         "{name} گرامی، عضویت رسمی شما در خانه تجارت عادلانه تأیید شد. گواهی به‌زودی صادر می‌شود." + S,
         "Dear {name}, your full membership was approved. Your certificate will be issued soon." + S_EN)
register("membership_status_member", "عضویت، به متقاضی: ثبت عضویت و صدور گواهی",
         "{name} گرامی، گواهی عضویت شما با شماره {certificate_number} صادر شد.\n{certificate_url}" + S,
         "Dear {name}, your membership certificate {certificate_number} has been issued.\n{certificate_url}" + S_EN)
register("membership_status_withdrawn", "عضویت، به متقاضی: بایگانی پرونده",
         "{name} گرامی، پرونده عضویت {code} بایگانی شد." + S,
         "Dear {name}, membership file {code} was archived." + S_EN, active=False)

register("membership_staff_new", "عضویت، به دبیرخانه: درخواست تازه",
         "درخواست عضویت تازه: {name} ({type})، کد {code}. مهلت بررسی: {deadline}\n{admin_url}",
         audience="secretariat")
register("membership_staff_resubmitted_secretariat", "عضویت، به دبیرخانه: متقاضی مدارک تکمیلی فرستاد",
         "متقاضی {name} ({code}) مدارک تکمیلی را فرستاد.\n{admin_url}", audience="secretariat")
register("membership_commission_new", "عضویت، به کمیسیون: پرونده برای ارزیابی",
         "پرونده عضویت {name} ({type}) برای ارزیابی به کمیسیون رسید. مهلت: {deadline}\n{admin_url}",
         audience="commission")
register("membership_staff_resubmitted_commission", "عضویت، به کمیسیون: متقاضی اصلاحات را فرستاد",
         "متقاضی {name} ({code}) اصلاحات خواسته‌شده را فرستاد.\n{admin_url}", audience="commission")
register("membership_reminder_secretariat", "عضویت، به دبیرخانه: یادآوری مهلت‌ها",
         "{count} پرونده عضویت نزدیک یا گذشته از مهلت است.\n{admin_url}", audience="secretariat")
register("membership_reminder_commission", "عضویت، به کمیسیون: یادآوری مهلت‌ها",
         "{count} پرونده عضویت در کمیسیون نزدیک یا گذشته از مهلت است.\n{admin_url}", audience="commission")
