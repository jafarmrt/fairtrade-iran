from sms.registry import register

register("complaint_new", "شکایت، به کمیسیون: شکایت تازه",
         "شکایت محرمانه تازه با کد {code} ثبت شد. متن آن فقط در پنل مدیریت است.\n{admin_url}",
         audience="commission")
register("contact_new", "تماس، به دبیرخانه: پیام تازه از فرم تماس",
         "پیام تازه از فرم «{form}» در سایت رسید. متن آن به ایمیل دبیرخانه فرستاده شد.",
         audience="secretariat", active=False)
