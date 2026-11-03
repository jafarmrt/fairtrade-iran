#!/bin/bash
# Free test copy of the site on PythonAnywhere (https://www.pythonanywhere.com),
# with demo data. Guide in Persian: docs/demo-fa.md. Not for the real site.
#
# In a PythonAnywhere Bash console (after creating the web app, see the guide):
#   git clone https://github.com/jafarmrt/fairtrade-iran.git ~/fairtrade-iran
#   bash ~/fairtrade-iran/deploy/pythonanywhere/setup.sh
#
# Run it again at any time to pull the latest code from GitHub and reload the
# site. Data (SQLite) is kept between runs; RESET=1 starts again from clean
# demo data. The demo password is asked once and kept in ~/fairtrade-demo.env.

set -euo pipefail

APP="${APP:-$HOME/fairtrade-iran}"
VENV="${VENV:-$HOME/.virtualenvs/fairtrade}"
ENV_FILE="${ENV_FILE:-$HOME/fairtrade-demo.env}"
DATA="${DATA:-$HOME/fairtrade-data}"
SITE_HOST="${SITE_HOST:-$(whoami).pythonanywhere.com}"
WSGI_FILE="${WSGI_FILE:-/var/www/${SITE_HOST//./_}_wsgi.py}"

say() { printf '\n==> %s\n' "$*"; }

PY=""
for candidate in python3.12 python3.13 python3.11 python3.10; do
    if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done
[ -n "$PY" ] || { echo "Python 3.10 or newer was not found."; exit 1; }

say "Getting the latest code"
git -C "$APP" pull --ff-only

say "Installing Python packages with $PY (a few minutes the first time)"
[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
# psycopg (PostgreSQL) is not needed here: the test copy uses SQLite. Saves disk space.
grep -v -i '^psycopg' "$APP/requirements.txt" > "$DATA.requirements.txt"
"$VENV/bin/pip" install --quiet --no-cache-dir --upgrade pip
"$VENV/bin/pip" install --quiet --no-cache-dir -r "$DATA.requirements.txt"
rm -f "$DATA.requirements.txt"

if [ ! -f "$ENV_FILE" ]; then
    say "Settings"
    password="${DEMO_PASSWORD:-}"
    while [ "${#password}" -lt 8 ]; do
        read -r -s -p "Choose a password for the demo logins (at least 8 characters): " password; echo
    done
    secret="$("$VENV/bin/python" -c 'import secrets; print(secrets.token_urlsafe(50))')"
    umask 077
    cat > "$ENV_FILE" <<ENV
DJANGO_SETTINGS_MODULE=fairtrade.settings.production
SECRET_KEY=$secret
DEMO_PASSWORD=$password
DEMO_MODE=1
PAYMENT_ALLOW_TEST_GATEWAY=1
ALLOWED_HOSTS=$SITE_HOST
CSRF_TRUSTED_ORIGINS=https://$SITE_HOST
SITE_URL=https://$SITE_HOST
DATABASE_URL=sqlite:///$DATA/demo.sqlite3
MEDIA_ROOT=$DATA/media
PRIVATE_MEDIA_ROOT=$DATA/private_media
STATIC_ROOT=$DATA/static
CACHE_DIR=$DATA/cache
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
SMS_BACKEND=sms.backends.ConsoleBackend
ENV
fi

set -a; . "$ENV_FILE"; set +a
mkdir -p "$DATA/media" "$DATA/private_media" "$DATA/static" "$DATA/cache"

if [ "${RESET:-0}" = "1" ]; then
    say "Removing the old demo data"
    rm -f "$DATA/demo.sqlite3"
fi

cd "$APP"
say "Preparing the database and demo content"
"$VENV/bin/python" manage.py migrate --noinput
"$VENV/bin/python" manage.py collectstatic --noinput -v0
"$VENV/bin/python" manage.py seed_demo

say "Connecting the web app"
cat > "$WSGI_FILE" <<PYWSGI
# Written by fairtrade-iran/deploy/pythonanywhere/setup.sh; run it again instead of editing.
import os
import sys

sys.path.insert(0, "$APP")
with open("$ENV_FILE") as fh:
    for line in fh:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key] = value

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
PYWSGI
touch "$WSGI_FILE"  # makes PythonAnywhere reload the site

say "Done"
cat <<DONE
Site:        https://$SITE_HOST
Admin:       https://$SITE_HOST/admin/   (demo-admin or demo-secretariat)
Member area: https://$SITE_HOST/fa/panel/ (demo-member)
Password:    the one you chose (stored in $ENV_FILE)

If the site still shows the PythonAnywhere welcome page, open the Web tab,
check that the Python version is ${PY#python} and Virtualenv is $VENV,
then press Reload.
DONE
