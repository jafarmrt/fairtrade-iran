"""SMS texts for the General Assembly (edited later in the admin: پیامک > متن‌های پیامک)."""

from sms.registry import register

S = "\n{site_name}"
S_EN = "\nFair Trade House of Iran"

register("assembly_invitation", "مجمع عمومی، به عضو: دعوت‌نامه",
         "{name} گرامی، به {assembly} در {date} دعوت شده‌اید. دستور جلسه و رأی‌گیری در پنل اعضا:\n{panel_url}" + S,
         "Dear {name}, you are invited to the {assembly} on {date}. Agenda and voting in the member panel:\n"
         "{panel_url}" + S_EN)
register("assembly_reminder", "مجمع عمومی، به عضو: یادآوری پیش از جلسه",
         "{name} گرامی، {assembly} در {date} برگزار می‌شود.\n{panel_url}" + S,
         "Dear {name}, the {assembly} takes place on {date}.\n{panel_url}" + S_EN)
register("assembly_voting", "مجمع عمومی، به عضو: آغاز رأی‌گیری",
         "{name} گرامی، رأی‌گیری «{item}» آغاز شد{closes}.\n{panel_url}" + S,
         "Dear {name}, voting on \"{item}\" is open{closes}.\n{panel_url}" + S_EN)
register("assembly_results", "مجمع عمومی، به عضو: اعلام نتایج",
         "{name} گرامی، نتایج {assembly} در پنل اعضا منتشر شد.\n{panel_url}" + S,
         "Dear {name}, the results of the {assembly} are in the member panel.\n{panel_url}" + S_EN)
