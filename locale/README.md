# Persian translations of the Wagtail admin

Wagtail ships Persian translations, but about half of its admin strings were
missing and some were awkward. `fa/LC_MESSAGES/django.po` (Python and template
strings) and `fa/LC_MESSAGES/djangojs.po` (the admin's JavaScript) complete and
correct them. Django reads `LOCALE_PATHS` before the apps' own catalogues, so
an entry here wins over Wagtail's.

## Changing a translation

1. Find the English text (`msgid`) in the `.po` file and change its `msgstr`.
   Keep every placeholder (`%(name)s`, `%s`, `{name}`) and HTML tag exactly as in
   the English; a placeholder the English does not have breaks the page.
2. Rebuild the compiled files and commit both the `.po` and the `.mo`:

   ```bash
   python manage.py build_translations
   ```

   It needs only Python (Django's `compilemessages` would need GNU gettext).
   `core/tests_admin_ui.py` fails if a `.mo` file is older than its `.po`.

## Word list

So that the whole admin speaks the same way:

| English | فارسی |
| --- | --- |
| Dashboard | پیشخوان |
| Page / Pages | صفحه / صفحه‌ها |
| Slug | نامک |
| Promote (tab) | سئو و منو |
| Draft / Publish / Unpublish | پیش‌نویس / انتشار / لغو انتشار |
| Revision | نسخه |
| Workflow / Task | گردش کار / مرحله |
| Comment | یادداشت |
| Locale | زبان |
| Alias | کپی همگام |
| Redirect | تغییر مسیر |
| Privacy | حریم خصوصی |
| Snippets | قطعه‌ها |
| Collection | مجموعه |
| Upload | بارگذاری |
| by (someone) | به‌دست |

Write «» for quotation marks and a zero-width non-joiner where Persian needs one
(صفحه‌ها, می‌شود). After a number, keep the noun singular («۲ صفحه», not «۲ صفحه‌ها»).

## After upgrading Wagtail

New Wagtail versions add strings. To list the admin's Python and template strings
that still have no Persian translation, run in `python manage.py shell`:

```python
from pathlib import Path
import wagtail
from django.utils import translation
from core import pofile
missing = set()
with translation.override("fa"):
    for po in Path(wagtail.__file__).parent.glob("**/locale/en/LC_MESSAGES/django.po"):
        for e in pofile.parse(po.read_text(encoding="utf-8")):
            if not e["id"] or e.get("plural"):
                continue
            ctxt = e.get("ctxt")
            text = translation.pgettext(ctxt, e["id"]) if ctxt else translation.gettext(e["id"])
            if text == e["id"]:
                missing.add(e["id"])
print("\n".join(sorted(missing)))
```

Add the ones that matter to `django.po` and run `build_translations`. Strings of
the admin's JavaScript are in Wagtail's `djangojs.po` files and go to our `djangojs.po`.
