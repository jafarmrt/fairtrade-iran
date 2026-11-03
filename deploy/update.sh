#!/usr/bin/env bash
# Update the site to the latest code on main, with a backup first.
# Run as root from the project folder:
#
#   sudo ./deploy/update.sh
#
set -euo pipefail
cd "$(dirname "$0")/.."

[ "$(id -u)" = 0 ] || { echo "run as root: sudo ./deploy/update.sh"; exit 1; }
[ -f .env ] || { echo "no .env here; run ./deploy/install.sh first"; exit 1; }

echo "==> Backup before updating"
docker compose run --rm backup now

echo "==> Fetching the latest code"
before="$(git rev-parse HEAD)"
git pull --ff-only
after="$(git rev-parse HEAD)"
if [ "$before" = "$after" ]; then
    echo "Already up to date."
fi

echo "==> Rebuilding and restarting (database changes run automatically)"
docker compose up -d --build --wait --wait-timeout 600

echo "==> Adding any new starting content"
docker compose exec -T web python manage.py seed_content >/tmp/fairtrade-seed.log 2>&1 \
    || { tail -20 /tmp/fairtrade-seed.log; exit 1; }

docker image prune -f >/dev/null
echo "Done: $(git log -1 --format='%h %s')"
