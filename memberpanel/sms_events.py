"""SMS texts of the member panel (edited later in the admin: پیامک > متن‌های پیامک)."""

from sms.registry import register

register("panel_login_code", "پنل اعضا: کد ورود یا تأیید موبایل",
         "کد ورود به پنل اعضای {site_name}: {code}\nاین کد تا {minutes} دقیقه معتبر است. آن را به کسی ندهید.",
         "Your Fair Trade House member panel code: {code}\nValid for {minutes} minutes. Do not share it.")
