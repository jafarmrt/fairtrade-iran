# خانه تجارت عادلانه ایران — Fair Trade House of Iran

وب‌سایت دوزبانه (فارسی/انگلیسی) خانه تجارت عادلانه ایران، ساخته‌شده با Django و Wagtail.

The bilingual (Persian/English) website of the Fair Trade House of Iran, built with Django 5.1 and Wagtail 6.3.

## Run it locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DJANGO_SETTINGS_MODULE=fairtrade.settings.dev
python manage.py migrate
python manage.py seed_content      # languages, starting pages, logos, groups, document collections
python manage.py createsuperuser
python manage.py runserver
```

- Site: http://localhost:8000/ (redirects to `/fa/`; English at `/en/`)
- Admin panel: http://localhost:8000/admin/ (in Persian)

`seed_content` is safe to run again: it only creates what is missing and never overwrites edits made in the admin panel.

## Run tests

```bash
DJANGO_SETTINGS_MODULE=fairtrade.settings.dev python manage.py test
```

## Deploy with Docker

On a fresh Ubuntu server, after cloning: `sudo ./deploy/install.sh` installs Docker and the firewall, sets up a Docker mirror if Docker Hub is blocked, writes `.env` with random secrets, starts the site, adds the starting content and an admin user, and turns on HTTPS once the domain points to the server. Re-running it is safe. `sudo ./deploy/update.sh` backs up, pulls and restarts.

راهنمای کامل فارسی استقرار روی سرور (VPS ایران یا خارج، HTTPS، پشتیبان‌گیری و بازگردانی): [docs/deploy-fa.md](docs/deploy-fa.md)

A test copy with demo data on your own computer, incl. WSL (`bash deploy/local/run-demo.sh`, `python manage.py seed_demo`): [docs/demo-fa.md](docs/demo-fa.md)

```bash
cp .env.example .env      # fill in SECRET_KEY, hosts, database password, email
docker compose up -d --build --wait
docker compose exec web python manage.py seed_content
docker compose exec web python manage.py createsuperuser
./deploy/init-https.sh admin@example.ir example.ir www.example.ir   # once, then set COMPOSE_FILE in .env
```

The stack is PostgreSQL + the app (gunicorn, static files via WhiteNoise) + nginx + a backup job, and runs the same on a server inside Iran or abroad. `docker-compose.https.yml` adds HTTPS with a Let's Encrypt certificate that renews itself.

**Backups:** the `backup` service dumps the database and archives the `media` and `private_media` volumes into `./backups/` every day (`BACKUP_TIME`, kept for `BACKUP_KEEP_DAYS`). Copy `./backups/` off the server regularly. Restore with `./deploy/restore.sh backups/<date-time>`.

**CI:** GitHub Actions runs the tests against PostgreSQL, checks migrations, runs `seed_content` twice, and builds and starts the Docker stack on every push to `main` and every pull request.

## What the admin panel controls

Nothing about the organisation is hard-coded. From **Settings** in the admin panel:

| Setting | What it holds |
| --- | --- |
| تنظیمات سایت (Site settings) | Names and taglines in both languages, logos (dark, light, English), contact details, social links, footer text, secretariat notification email |
| تنظیمات عضویت (Membership settings) | Application fee and annual fee per member type, bank account for payments, review deadlines (7 / 30 days), trial period (3 months), applications open or closed |
| نسخه موبایلی (Phone version / PWA) | Installable-app name, icon and colours, install prompt text, offline page; see [docs/pwa-fa.md](docs/pwa-fa.md) |

Pages (home, about, principles, and later news, members, shop) are edited under **Pages**. Each page has a Persian and an English version; use **Translate** on a Persian page to create its English copy.

## Project layout

| App | Purpose |
| --- | --- |
| `fairtrade/` | Settings, URLs, base templates, CSS, fonts, default logos |
| `core/` | Site and membership settings, shared StreamField blocks, `tr` template tag for bilingual fields |
| `home/` | Home page model and the `seed_content` command |
| `pages/` | General content page and the Ten Principles page |
| `search/` | Site search, limited to the current language |
| `membership/` | Membership page, application forms, tracking, secretariat/commission workflow, certificates |
| `memberpanel/` | Member panel: sign-in, profile and product editing for members, onboarding of new members |

## Access and privacy

User groups mirror the governance document: دبیرخانه (secretariat), کمیسیون نظارتی (supervisory commission), هیئت مدیره (board), روابط عمومی (PR), اعضا (members).

Documents live in four collections. Files in a restricted collection are only served to logged-in users in the allowed groups:

| Collection | Who can download |
| --- | --- |
| اسناد عمومی | Everyone |
| اسناد اعضا | Members, secretariat, board, commission |
| اسناد هیئت مدیره | Board, secretariat, commission |
| اسناد کمیسیون نظارتی | Commission only |

Files uploaded with membership applications must go to `PRIVATE_MEDIA_ROOT`, which is never served by nginx.

## Fonts

The brand typeface is IRANSans, which is commercially licensed. The site ships with Vazirmatn (SIL Open Font License) as a free fallback. If the house holds an IRANSans web licence, add the font files to `fairtrade/static/fonts/` and an `@font-face` rule for `"IRANSans"` in `fairtrade.css`; it is already first in the font stack.

## Membership workflow

The membership page (`/fa/membership/`, `/en/membership/`) shows benefits, member types, fees (from **Settings › تنظیمات عضویت**) and the admission steps. Each member type has its own form at `apply/<type>/`; the questions are snippets under **عضویت › پرسش‌های فرم**. Applicants get a tracking code and can follow their file at `track/`, where they also send missing documents. Anyone can check a certificate at `certificate/?number=…`.

Staff work under **عضویت › پرونده‌های عضویت**. The process follows section 1.4 of the governance document:

| Status | Who acts | Deadline |
| --- | --- | --- |
| در انتظار کنترل مدارک | Secretariat: confirm fee, report missing documents, or forward to commission | `secretariat_review_days` |
| ارزیابی کمیسیون | Commission: record field visit (required for producers), then trial / request fix / reasoned rejection | `commission_review_days` |
| عضو آزمایشی | Commission at the end: full member / one-off extension / not accepted | `trial_period_months` |
| تأیید عضویت رسمی | Secretariat: register and issue the certificate (printable in Persian and English) | `secretariat_review_days` |

Only users in a group with the permission «اقدامات دبیرخانه» or «ثبت رأی کمیسیون» can act; `seed_content` gives these to the دبیرخانه and کمیسیون نظارتی groups. Uploaded files go to `PRIVATE_MEDIA_ROOT/membership/` and are downloaded only through the admin.

E-mail texts are editable under **عضویت › ایمیل‌ها**. Deadline reminders (`python manage.py membership_reminders`) run once a day in the `scheduler` service of `docker-compose.yml`, at `DAILY_JOBS_TIME` (default 08:00 Tehran time). Without Docker, run that command from cron.

### Annual fees, suspension and cancellation

App `standing` (governance doc 1.7, 1.8, 7, 8.2). Amounts are the annual fees in **Settings › تنظیمات عضویت**; the tab «حق عضویت سالانه و تعلیق» sets the membership year (fixed Jalali date or joining anniversary), billing, reminder and payment days, automatic written warning, suspension N months after the warning, maximum suspension, appeal days and reapply periods. `python manage.py membership_standing` (run daily by the scheduler, with `--today YYYY-MM-DD` for testing) issues dues, reminds, warns, suspends and e-mails a digest to the secretariat and commission. Members pay and upload receipts at `/fa/panel/<id>/membership/`; staff work in **وضعیت اعضا و حق عضویت** (confirm/reject receipts, record payments, waive, notices, warnings, suspension, lifting, cancellation, reinstatement). Receipts are private files under `PRIVATE_MEDIA_ROOT/dues/`.

When the secretariat registers a full member, the signal `membership.workflow.member_registered` is sent (with `application` and `certificate`) so a members directory can create the public profile.

## Member panel

Members manage their own public profile and products at `/fa/panel/` (`/en/panel/`), app `memberpanel`.

- **Who can use it:** any user listed under "کاربرانی که این عضو را مدیریت می‌کنند" on a member (Snippets → اعضا و فروشگاه → اعضا). They are added to the «اعضا» group automatically, so they can also open member-only documents. Sign-in works with e-mail or username.
- **New members:** when the commission accepts a file for the trial period (or the secretariat registers a full member), the member profile is created from the application, a panel account is made for the applicant's e-mail and an invitation is sent with a link to choose a password. "Not accepted" suspends and hides the profile. The invitation text is the «دعوت به پنل اعضا» e-mail template.
- **What members can change:** names, introductions and story (fa/en), region and city, logo and main photo, contact and shop links, and their products (text, price, stock, photos, show/hide, delete). Type, status, founding flag, featured and order stay with the secretariat. Every change is in the item's history in the admin.
- **Review:** new products are hidden and marked «در انتظار بررسی» until staff untick it; the review address gets an e-mail. Filter products by that field in the admin.
- **Settings → پنل اعضا:** switch the panel on/off, welcome/login/help texts, whether new products need review, limits on products and photos, whether members may delete, and how profiles are created for new members.
- Photos uploaded from the panel go to the «تصاویر اعضا» image collection.
