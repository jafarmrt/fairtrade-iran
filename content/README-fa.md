# بستهٔ محتوای دوزبانهٔ سایت

همهٔ متن‌های سایت خانه تجارت عادلانه ایران، به فارسی و انگلیسی، در همین پوشه است؛ جدا از کد برنامه.
برای تغییر متن‌های روزمره کافی است آن را در پنل مدیریت ویرایش کنید. این پوشه برای راه‌اندازی سایت تازه،
بازگرداندن متن‌ها، و درون‌ریزی یک‌جای متن‌های بازبینی‌شده است.

| فایل | چه چیزی در آن است |
| --- | --- |
| `site.yaml` | نام و شعار سایت، متن پانویس، ایمیل و شبکه‌های اجتماعی، توضیح سئو، عنوان بخش‌های صفحهٔ اصلی، متن گواهی عضویت |
| `pages/NNN-key.yaml` | هر صفحه در یک فایل، فارسی و انگلیسی کنار هم: صفحهٔ اصلی، درباره ما، تجارت عادلانه چیست، اصول ده‌گانه، اعضا، فروشگاه، عضویت، اخبار، اسناد، تماس، شکایت، خرید عمده، حریم خصوصی، قوانین، بازگشت کالا |
| `members.yaml` | استان‌ها، دسته‌های فروشگاه، اعضای مؤسس با معرفی کامل، و اعضایی که دیگر عضو مؤسس نیستند (`withdrawn`) |
| `membership-form.yaml` | پرسش‌های فرم درخواست عضویت، برای هر نوع عضویت |
| `emails.yaml` | متن ایمیل‌های عضویت، حق عضویت، پنل اعضا و فروشگاه |
| `sms.yaml` | متن پیامک‌ها |
| `checks.yaml` | عبارت‌هایی که نباید دیگر در سایت باشند (مثل نام عضوی که دیگر مؤسس نیست) |

## درون‌ریزی از پنل مدیریت (ساده‌ترین راه)

فقط برای مدیر کل سایت (superuser):

1. در پنل مدیریت به **تنظیمات › درون‌ریزی محتوا** بروید.
2. اگر فایل zip تازه‌ای از این پوشه دارید آن را انتخاب کنید؛ وگرنه بستهٔ همراه سایت به کار می‌رود.
3. یکی را انتخاب کنید:
   - **فقط افزودن موارد تازه**: آنچه در سایت نیست ساخته می‌شود و به ویرایش‌های پنل دست نمی‌زند.
   - **جایگزینی متن‌ها**: متن بسته جای متن فعلی صفحه‌ها، اعضا، پرسش‌ها، ایمیل‌ها و تنظیمات را می‌گیرد.
     از هر صفحه نسخهٔ تازه منتشر می‌شود و نسخهٔ قبلی در «تاریخچه»ی صفحه می‌ماند.
4. اول **پیش‌نمایش** را بزنید و فهرست تغییرها را ببینید (چیزی ذخیره نمی‌شود)، بعد **درون‌ریزی**.

## درون‌ریزی با فرمان (روی سرور)

```bash
python manage.py import_content --update --dry-run   # پیش‌نمایش
python manage.py import_content --update             # درون‌ریزی و جایگزینی متن‌ها
```

با Docker:

```bash
docker compose exec web python manage.py import_content --update --dry-run
docker compose exec web python manage.py import_content --update
```

- بدون `--update` فقط موارد تازه اضافه می‌شود (مثل `seed_content`).
- برای بستهٔ دیگری مسیر پوشه یا فایل zip را بدهید: `python manage.py import_content /path/content.zip --update`
- روی پایگاه دادهٔ خالی هم کار می‌کند: پیش از متن‌ها، زبان‌ها، صفحهٔ اصلی، گروه‌های کاربری و مجموعه‌های اسناد را می‌سازد.

## بررسی درستی درون‌ریزی

1. در پایان هر درون‌ریزی خلاصه‌ای مثل `Done: 3 created, 12 updated` چاپ می‌شود و هشدارها (warning) زیر آن می‌آید.
2. اجرای دوبارهٔ `python manage.py import_content --update --dry-run` باید بگوید `nothing to change`.
3. `python manage.py import_content --check` جاهایی را که هنوز عبارت‌های `checks.yaml` در آن‌هاست فهرست می‌کند؛
   باید بگوید `No listed phrase found.` (صفحهٔ «درون‌ریزی محتوا» هم همین فهرست را نشان می‌دهد).
4. چند صفحه را در `/fa/` و `/en/` باز کنید: درباره ما، تجارت عادلانه چیست، اصول ده‌گانه، اعضا (گزینهٔ «اعضای مؤسس»).

## ویرایش فایل‌ها

- فایل‌ها YAML و UTF-8 هستند. هر ویرایشگر متنی (مثلاً VS Code یا Notepad++) کافی است؛ تورفتگی‌ها (فاصلهٔ اول خط) مهم‌اند.
- متن بلند بعد از `>-` می‌آید و می‌تواند چند خط باشد؛ خط‌ها با فاصله به هم می‌چسبند. بعد از `|-` شکست خط حفظ می‌شود.
- متن صفحه‌ها (`body`) فهرستی از بخش‌هاست: `heading` (سرتیتر)، `paragraph` (پاراگراف با HTML ساده مثل `<p>` و `<b>` و `<ul>`)،
  `cards` (ردیف کارت)، `quote` (نقل قول).
- `slug` بخش پایانی نشانی صفحه است؛ پس از انتشار آن را عوض نکنید.
- پرسش‌های فرم با متن فارسی‌شان شناخته می‌شوند: اگر متن پرسشی را عوض کنید، پرسش تازه‌ای ساخته می‌شود و پرسش قدیمی را باید
  در پنل (عضویت › پرسش‌های فرم عضویت) غیرفعال کنید.
- عضوی که دیگر عضو مؤسس نیست را زیر `withdrawn` در `members.yaml` بنویسید و نامش را به `checks.yaml` اضافه کنید.
- لوگوها، عکس‌ها، شمارهٔ حساب، مبلغ‌ها و تنظیمات فنی در این بسته نیستند و فقط در پنل مدیریت تنظیم می‌شوند.
- برای ساختن zip: روی پوشهٔ `content` راست‌کلیک کنید و «فشرده‌سازی» را بزنید؛ zip باید خود پوشهٔ `content` یا محتوای آن را داشته باشد.

---

## English summary

All texts of the site, in Persian and English, live in this folder as YAML, separate from the code.
Day-to-day edits are made in the admin panel; this package is for setting up a new site, restoring texts, or
loading a reviewed set of texts in one go.

**Import from the admin panel** (superusers): Settings › «درون‌ریزی محتوا». Optionally upload a .zip of this
folder, choose "add only what is missing" or "replace texts", press Preview (nothing is saved), then Import.

**Import from the command line:**

```bash
python manage.py import_content --update --dry-run   # preview
python manage.py import_content --update             # import, replacing existing texts
python manage.py import_content --check              # list places where phrases from checks.yaml still appear
```

Without `--update`, only missing items are created (this is what `seed_content` does on every deploy, so admin
edits are never overwritten). With `--update`, pages get a new published revision; the previous text stays in the
page history. The command also works on an empty database.

**Verify:** the command ends with a summary line and any warnings; a second `--update --dry-run` reports
`nothing to change`; `--check` reports `No listed phrase found.`; open the pages in `/fa/` and `/en/`.
