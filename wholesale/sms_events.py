from sms.registry import register

register("wholesale_new", "سفارش عمده، به دبیرخانه: درخواست تازه",
         "درخواست سفارش عمده {code} از {company} ({country}) رسید.\n{admin_url}",
         audience="secretariat")
register("wholesale_producer", "سفارش عمده، به تولیدکننده: درخواست تازه برای محصولات شما",
         "{name} گرامی، درخواست سفارش عمده {code} از {country} برای محصولات شما رسید. "
         "لطفاً در پنل اعضا پاسخ دهید:\n{panel_url}",
         "Dear {name}, wholesale enquiry {code} from {country} includes your products. "
         "Please reply in the member panel:\n{panel_url}")
register("wholesale_reply", "سفارش عمده، به دبیرخانه: پاسخ تولیدکننده",
         "{name} به درخواست سفارش عمده {code} پاسخ داد: {status}.\n{admin_url}",
         audience="secretariat")
