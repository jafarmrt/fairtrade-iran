"""SMS texts for annual dues and member standing (edited later in the admin: پیامک > متن‌های پیامک)."""

from sms.registry import register

S = "\n{site_name}"
S_EN = "\nFair Trade House of Iran"

register("dues_issued", "حق عضویت، به عضو: صورت‌حساب سالانه",
         "{name} گرامی، حق عضویت سال {year}: {amount}، مهلت پرداخت {due_date}.\n{panel_url}" + S,
         "Dear {name}, membership fee {year}: {amount}, due by {due_date}.\n{panel_url}" + S_EN)
register("dues_reminder", "حق عضویت، به عضو: یادآوری پرداخت",
         "{name} گرامی، مهلت پرداخت حق عضویت سال {year} تا {due_date} است.\n{panel_url}" + S,
         "Dear {name}, your membership fee for {year} is due by {due_date}.\n{panel_url}" + S_EN)
register("dues_warning", "حق عضویت، به عضو: اخطار کتبی",
         "{name} گرامی، حق عضویت سال {year} پرداخت نشده است. اخطار کتبی به ایمیل شما فرستاده شد؛ "
         "اگر تا {suspend_date} پرداخت نشود، عضویت تعلیق می‌شود.\n{panel_url}" + S,
         "Dear {name}, your membership fee for {year} is unpaid. A written warning was e-mailed to you; "
         "without payment by {suspend_date} your membership will be suspended.\n{panel_url}" + S_EN)
register("dues_confirmed", "حق عضویت، به عضو: پرداخت تأیید شد",
         "{name} گرامی، پرداخت حق عضویت سال {year} تأیید شد. سپاس." + S,
         "Dear {name}, your membership fee for {year} has been confirmed. Thank you." + S_EN)
register("dues_rejected", "حق عضویت، به عضو: رسید پذیرفته نشد",
         "{name} گرامی، رسید حق عضویت سال {year} پذیرفته نشد. جزئیات در ایمیل و پنل شماست.\n{panel_url}" + S,
         "Dear {name}, your receipt for {year} was not accepted. Details are in your e-mail.\n{panel_url}" + S_EN)
register("dues_receipt_staff", "حق عضویت، به دبیرخانه: رسید تازه",
         "رسید حق عضویت سال {year} «{member}» رسید و منتظر تأیید است.\n{admin_url}",
         audience="secretariat")
register("standing_suspend", "وضعیت عضو، به عضو: تعلیق عضویت",
         "{name} گرامی، عضویت شما تا {until} تعلیق شد. جزئیات و مهلت اعتراض در ایمیل شماست." + S,
         "Dear {name}, your membership is suspended until {until}. Details and the appeal deadline are in "
         "your e-mail." + S_EN)
register("standing_lift", "وضعیت عضو، به عضو: رفع تعلیق",
         "{name} گرامی، تعلیق عضویت شما رفع شد." + S,
         "Dear {name}, the suspension of your membership has been lifted." + S_EN)
register("standing_cancel", "وضعیت عضو، به عضو: لغو عضویت",
         "{name} گرامی، عضویت شما لغو شد. جزئیات و مهلت اعتراض در ایمیل شماست." + S,
         "Dear {name}, your membership has been cancelled. Details and the appeal deadline are in your e-mail."
         + S_EN)
