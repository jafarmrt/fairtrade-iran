#!/bin/bash
# Test copy of the site on your own computer (Linux, macOS or WSL on Windows),
# with demo data. Guide in Persian: docs/demo-fa.md. Not for the real site.
#
#   git clone https://github.com/jafarmrt/fairtrade-iran.git ~/fairtrade-iran
#   bash ~/fairtrade-iran/deploy/local/run-demo.sh
#
# Then open http://localhost:8000 in the browser. Ctrl+C stops the site; run the
# script again to start it (it also pulls the latest code). Data is kept in
# demo.sqlite3; RESET=1 starts again from clean demo data.
# Demo logins: demo-admin, demo-secretariat, demo-member; password DEMO_PASSWORD
# (default below).

set -euo pipefail

APP="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="$APP/.venv"
PORT="${PORT:-8000}"
export DEMO_PASSWORD="${DEMO_PASSWORD:-demo12345}"

say() { printf '\n==> %s\n' "$*"; }

PY=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 \
        && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
        PY="$candidate"; break
    fi
done
if [ -z "$PY" ]; then
    echo "Python 3.10 or newer is needed. On Ubuntu/WSL: sudo apt install python3 python3-venv"
    exit 1
fi

cd "$APP"
if git rev-parse --git-dir >/dev/null 2>&1; then
    say "Getting the latest code"
    git pull --ff-only || echo "(could not pull; using the code as it is)"
fi

if [ ! -x "$VENV/bin/python" ]; then
    say "Creating the Python environment with $PY"
    if ! "$PY" -m venv "$VENV"; then
        rm -rf "$VENV"
        echo "Could not create it. On Ubuntu/WSL run:  sudo apt install python3-venv  and try again."
        exit 1
    fi
fi

say "Installing Python packages (a few minutes the first time)"
# psycopg (PostgreSQL) is not needed: the test copy uses SQLite.
grep -v -i '^psycopg' requirements.txt > "$VENV/requirements-demo.txt"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$VENV/requirements-demo.txt"

export DJANGO_SETTINGS_MODULE=fairtrade.settings.dev
export DEMO_MODE=1
export DATABASE_URL="sqlite:///$APP/demo.sqlite3"
export PYTHONUTF8=1

if [ "${RESET:-0}" = "1" ]; then
    say "Removing the old demo data"
    rm -f "$APP/demo.sqlite3"
fi

say "Preparing the database and demo content"
"$VENV/bin/python" manage.py migrate --noinput -v0
"$VENV/bin/python" manage.py seed_demo >/dev/null

cat <<DONE

==> The site is starting. Open in your browser:
    Site:        http://localhost:$PORT/fa/
    Admin:       http://localhost:$PORT/admin/    (demo-admin or demo-secretariat)
    Member area: http://localhost:$PORT/fa/panel/ (demo-member)
    Password:    $DEMO_PASSWORD
    Press Ctrl+C here to stop it.

DONE
exec "$VENV/bin/python" manage.py runserver "127.0.0.1:$PORT"
