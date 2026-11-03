"""SMS texts for shop orders (edited later in the admin: پیامک > متن‌های پیامک)."""

from sms.registry import register

S = "\n{site_name}"
S_EN = "\nFair Trade House of Iran"

register("order_placed", "فروشگاه، به خریدار: سفارش ثبت شد",
         "{name} گرامی، سفارش {code} ثبت شد. مبلغ: {total}. راهنمای پرداخت:\n{order_url}" + S,
         "Dear {name}, your order {code} is placed. Total: {total}. How to pay:\n{order_url}" + S_EN)
register("order_paid", "فروشگاه، به خریدار: پرداخت تأیید شد",
         "{name} گرامی، پرداخت سفارش {code} ({member}) تأیید شد و آماده ارسال می‌شود." + S,
         "Dear {name}, payment for order {code} ({member}) is confirmed; it is being prepared." + S_EN)
register("order_rejected", "فروشگاه، به خریدار: پرداخت تأیید نشد",
         "{name} گرامی، پرداخت سفارش {code} تأیید نشد: {message}\n{order_url}" + S,
         "Dear {name}, payment for order {code} could not be confirmed: {message}\n{order_url}" + S_EN)
register("order_shipped", "فروشگاه، به خریدار: سفارش ارسال شد",
         "{name} گرامی، سفارش {code} ({member}) ارسال شد. کد رهگیری: {tracking}" + S,
         "Dear {name}, order {code} ({member}) has been shipped. Tracking: {tracking}" + S_EN)
register("order_cancelled", "فروشگاه، به خریدار و فروشنده: سفارش لغو شد",
         "سفارش {code} ({member}) لغو شد: {message}" + S,
         "Order {code} ({member}) was cancelled: {message}" + S_EN)
register("order_refunded", "فروشگاه، به خریدار: مرجوعی و بازپرداخت ثبت شد",
         "{name} گرامی، بازپرداخت سفارش {code} ({member}) ثبت شد." + S,
         "Dear {name}, the refund for order {code} ({member}) is recorded." + S_EN)
register("order_return_request", "فروشگاه، به فروشنده و دبیرخانه: درخواست مرجوعی",
         "خریدار برای سفارش {code} درخواست مرجوعی داد: {message}", audience="secretariat")
register("order_seller_new", "فروشگاه، به فروشنده: سفارش تازه",
         "سفارش تازه {code} در سایت خانه: {total}، پرداخت به {payment_mode}.\n{panel_url}")
register("order_seller_paid", "فروشگاه، به فروشنده: پرداخت شد، ارسال کنید",
         "پرداخت سفارش {code} تأیید شد؛ لطفاً ارسال کنید و کد رهگیری را در پنل ثبت کنید.\n{panel_url}")
register("order_receipt", "فروشگاه، به دبیرخانه یا فروشنده: رسید پرداخت تازه",
         "رسید پرداخت سفارش {code} رسید و منتظر تأیید است.\n{admin_url}", audience="secretariat")
register("order_staff_new", "فروشگاه، به دبیرخانه: سفارش تازه",
         "سفارش تازه {code} در فروشگاه: {total}.\n{admin_url}", audience="secretariat", active=False)
register("order_seller_receipt", "فروشگاه، به فروشنده: خریدار پرداخت را خبر داد",
         "خریدار سفارش {code} اطلاعات پرداخت را فرستاد؛ پس از دیدن واریز، در پنل تأیید کنید.\n{panel_url}")
