"""
Names of user groups, document collections and the editorial workflow that
seed_content creates (they mirror the bodies of the governance document).

The texts of the site are not here: they are in the content package, the
content/ folder (see content/README-fa.md and `python manage.py import_content`).
"""


# Groups mirror the bodies in the governance document.
SECRETARIAT = "دبیرخانه"
COMMISSION = "کمیسیون نظارتی"
BOARD = "هیئت مدیره"
PR = "روابط عمومی"
MEMBERS_GROUP = "اعضا"
ASSEMBLY_SECRETARY = "دبیر مجمع"  # secretary of the general assembly and deputy; hears appeals (section 8.2)
MARKET = "کارگروه توسعه بازار"  # market development working group: wholesale enquiries, shop orders, settlement
# Pages written by the PR group go live after the board approves them (Settings > Workflows to change).
# Title of the page tree's top page (above «خانه» and «Home»), as the admin's page browser shows it.
ROOT_TITLE = "همهٔ صفحه‌ها"
EDITORIAL_WORKFLOW = "تأیید انتشار محتوا"
EDITORIAL_TASK = "تأیید هیئت مدیره"
GROUPS = [SECRETARIAT, COMMISSION, BOARD, PR, MEMBERS_GROUP, ASSEMBLY_SECRETARY, MARKET]

# Document collections and who may download their files.
# An empty list means public.
COLLECTIONS = [
    ("اسناد عمومی", []),
    ("اسناد اعضا", [MEMBERS_GROUP, SECRETARIAT, BOARD, COMMISSION]),
    ("اسناد هیئت مدیره", [BOARD, SECRETARIAT, COMMISSION]),
    ("اسناد کمیسیون نظارتی", [COMMISSION]),
    ("تصاویر اعضا", []),  # photos members upload from the member panel
]

# Which document collections each group may upload to and edit in the admin.
# Kept to the collections the group may also open: someone who can edit a
# document can move it to another collection, so edit rights on a private
# collection would let them publish its files.
DOCUMENT_EDITORS = {
    PR: ["اسناد عمومی"],
    BOARD: ["اسناد عمومی", "اسناد اعضا", "اسناد هیئت مدیره"],
    SECRETARIAT: ["اسناد عمومی", "اسناد اعضا", "اسناد هیئت مدیره"],
    COMMISSION: ["اسناد کمیسیون نظارتی"],
}
