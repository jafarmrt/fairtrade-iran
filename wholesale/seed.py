"""Starting content for wholesale enquiries; called by seed_content. Idempotent."""

from django.contrib.auth.models import Group, Permission

from home.management.commands import seed_data

from .models import WholesalePage

PAGE = {
    "fa": {
        "title": "خرید عمده و صادرات",
        "slug": "wholesale",
        "intro": "<p>فروشگاه، واردکننده یا سازمان تجارت عادلانه هستید؟ محصولات اعضای خانه را به‌صورت عمده سفارش دهید. "
                 "خانه درخواست شما را با تولیدکنندگان هماهنگ می‌کند و پیشنهاد قیمت می‌فرستد.</p>",
        "form_intro": "<p>این اطلاعات فقط برای پاسخ به درخواست شما به‌کار می‌رود.</p>",
        "side_note": "<ul><li>کمترین مقدار سفارش برای هر محصول متفاوت است و در پیشنهاد قیمت می‌آید.</li>"
                     "<li>بیشتر محصولات دست‌ساز است و چند هفته زمان آماده‌سازی دارد.</li>"
                     "<li>معمولاً ظرف چند روز کاری پاسخ می‌دهیم.</li></ul>",
        "thank_you_text": "<p>سپاس؛ درخواست شما به خانه تجارت عادلانه ایران رسید. موجودی، قیمت و زمان آماده‌سازی را "
                          "با تولیدکنندگان بررسی می‌کنیم و به‌زودی پاسخ می‌دهیم.</p>",
    },
    "en": {
        "title": "Wholesale and export",
        "slug": "wholesale",
        "intro": "<p>Are you a shop, an importer or a fair trade organisation? Order our members' handmade products "
                 "wholesale. The House coordinates your enquiry with the producers and sends you a quotation.</p>",
        "form_intro": "<p>We use these details only to answer your enquiry.</p>",
        "side_note": "<ul><li>Minimum order quantities vary by product and are given in the quotation.</li>"
                     "<li>Most products are handmade and need a few weeks to prepare.</li>"
                     "<li>We usually reply within a few working days.</li></ul>",
        "thank_you_text": "<p>Thank you. Your enquiry has reached the Fair Trade House of Iran. We will check "
                          "availability, prices and lead times with the producers and get back to you soon.</p>",
    },
}

INQUIRY_PERMS = ["view_wholesaleinquiry", "change_wholesaleinquiry", "add_wholesaleinquiry"]
HANDLER_GROUPS = [seed_data.SECRETARIAT, seed_data.MARKET]


def ensure_wholesale(command, home_fa, home_en):
    from home.management.commands.seed_content import fresh

    page_fa = WholesalePage.objects.filter(locale=home_fa.locale).first()
    if page_fa is None:
        # Not in the Persian menu (linked from the shop instead); in the English menu, for foreign buyers.
        page_fa = WholesalePage(show_in_menus=False, **PAGE["fa"])
        fresh(home_fa).add_child(instance=page_fa)
        page_fa.save_revision().publish()
        command.stdout.write("Created wholesale page (fa)")
    if fresh(page_fa).get_translation_or_none(home_en.locale) is None:
        command.ensure_translation(page_fa, home_en.locale, dict(PAGE["en"], show_in_menus=True), "wholesale page")

    perms = list(Permission.objects.filter(content_type__app_label="wholesale", codename__in=INQUIRY_PERMS))
    settings_perm = Permission.objects.filter(content_type__app_label="wholesale",
                                              codename="change_wholesalesettings").first()
    for name in HANDLER_GROUPS:
        group = Group.objects.filter(name=name).first()
        if group is None:
            continue
        group.permissions.add(*perms)
        if settings_perm is not None:
            group.permissions.add(settings_perm)
