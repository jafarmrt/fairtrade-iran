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

راهنمای کامل فارسی استقرار روی سرور (VPS ایران یا خارج، HTTPS، پشتیبان‌گیری و بازگردانی): [docs/deploy-fa.md](docs/deploy-fa.md)

```bash
cp .env.example .env      # fill in SECRET_KEY, hosts, database password, email
docker compose up -d --build
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

Pages (home, about, principles, and later news, members, shop) are edited under **Pages**. Each page has a Persian and an English version; use **Translate** on a Persian page to create its English copy.

## Project layout

| App | Purpose |
| --- | --- |
| `fairtrade/` | Settings, URLs, base templates, CSS, fonts, default logos |
| `core/` | Site and membership settings, shared StreamField blocks, `tr` template tag for bilingual fields |
| `home/` | Home page model and the `seed_content` command |
| `pages/` | General content page and the Ten Principles page |
| `search/` | Site search, limited to the current language |

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
