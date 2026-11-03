# Working on this repo

Website of the Fair Trade House of Iran (خانه تجارت عادلانه ایران). Django 5.2 + Wagtail 7.4 (both LTS), Persian first (RTL) with English.
The plan and requirements are in the project's plan document; the governance document (`سند ارکان`, v2, Mehr 1405) defines membership rules and bodies.

## Conventions

- **Everything the organisation might change is editable in the admin panel.** Never hard-code fees, deadlines, bank details, logos, contact info, member data or form questions. Add a field to `core.models.MembershipSettings` / `SiteSettings`, or a model/page, instead.
- **Bilingual content:**
  - Wagtail pages: one page tree per locale (`/fa/…`, `/en/…`), linked as translations. Create English pages with `copy_for_translation`.
  - Plain Django models (members, products, …): store Persian in `field` and English in `field_en`, inherit `core.models.BilingualMixin`, and render with `{% tr obj "field" %}`. In English listings, hide items whose `name_en` is empty.
- **UI text in templates:** use `{% if IS_EN %}English{% else %}فارسی{% endif %}` (context processor `core.context_processors.site_context` provides `LANG`, `IS_EN`, `DIR`).
- **Admin labels** (verbose_name, panel headings, help_text) are in Persian.
- **Admin panel for volunteers:** the admin's look (font, brand colours, logo) is `fairtrade/static/css/admin.css` and `core/templates/wagtailadmin/`; the main-menu and settings-menu order, hidden technical items, dashboard shortcuts and the Persian guide (`/admin/guide/`) are in `core/wagtail_hooks.py` and `core/admin_views.py`. Put a new admin listing in an existing menu group (`عضویت`, `اعضا`, `فروشگاه`, …), give a new top-level item a `menu_name` and a place in `MAIN_MENU_ORDER`, and mention new daily tasks in the guide.
- **Admin translations:** `locale/fa/LC_MESSAGES/*.po` complete Wagtail's Persian; after editing, run `python manage.py build_translations` and commit the `.mo` too (see `locale/README.md`).
- **Upgrades:** stay on Django and Wagtail LTS releases (`WAGTAIL_ENABLE_UPDATE_CHECK = "lts"`).
- **CSS:** one file for the site, `fairtrade/static/css/fairtrade.css` (the admin has its own theme, `admin.css`). Use the existing tokens (`--gold`, `--navy`, `--brown`, …) and logical properties (`margin-inline-start`, not `margin-left`) so RTL and LTR both work. Reuse `.section`, `.page-header`, `.grid`, `.card`, `.btn`, `.form`.
- **Private files** (application documents, receipts) go to `settings.PRIVATE_MEDIA_ROOT` through a storage of their own and are served only by a staff-checked view, never from `MEDIA_ROOT`.
- **Access levels** use the groups and document collections created by `seed_content` (see `home/management/commands/seed_data.py`).
- **Seed data:** extend `seed_content` so a fresh install has sensible content; it must stay idempotent.

## Checks before pushing

```bash
export DJANGO_SETTINGS_MODULE=fairtrade.settings.dev
python manage.py makemigrations --check --dry-run
python manage.py test
```

Look at changed pages in both `/fa/` and `/en/`, at desktop and phone width.
