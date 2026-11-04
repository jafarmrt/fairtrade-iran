#!/usr/bin/env bash
# Makes the two PDF guides again from a fresh demo site: demo data, screenshots, PDFs.
# Run from anywhere:  bash docs/guides/make.sh
# Needs: the project's .venv, Node.js with Playwright (npm i -g playwright && npx playwright install chromium),
#        python3 with pypdf (pip install pypdf).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$ROOT"
mkdir -p "$HERE/work" "$HERE/shots"
export DJANGO_SETTINGS_MODULE=fairtrade.settings.dev PYTHONUTF8=1
export DATABASE_URL="sqlite:///$HERE/work/guide-demo.sqlite3"
PY="$ROOT/.venv/bin/python"

echo "1/4 demo data"
rm -f "$HERE/work/guide-demo.sqlite3"
"$PY" manage.py migrate -v0
DEMO_PASSWORD=demo12345 "$PY" manage.py seed_demo
"$PY" manage.py update_index -v0 || true
"$PY" manage.py shell < "$HERE/extra_demo.py"

echo "2/4 demo server"
"$PY" manage.py runserver --noreload 127.0.0.1:8000 > "$HERE/work/server.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
for _ in $(seq 30); do curl -sf -o /dev/null http://127.0.0.1:8000/fa/ && break; sleep 1; done

echo "3/4 screenshots"
node "$HERE/shoot.js"

echo "4/4 PDFs"
node "$HERE/build.js" "$HERE/admin.html" "$HERE/admin-guide-fa.pdf"
node "$HERE/build.js" "$HERE/user.html" "$HERE/user-guide-fa.pdf"
echo "done: $HERE/admin-guide-fa.pdf  $HERE/user-guide-fa.pdf"
