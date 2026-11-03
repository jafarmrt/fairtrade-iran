#!/bin/sh
# Restore a backup made by backup.sh. This REPLACES the current database
# and uploaded files. Run from the project folder on the server:
#
#   ./deploy/restore.sh backups/2026-11-02_0330
#
set -eu

dir="${1:?usage: deploy/restore.sh backups/<date-time>}"
for f in db.dump media.tar.gz private_media.tar.gz; do
    [ -f "$dir/$f" ] || { echo "missing $dir/$f"; exit 1; }
done

printf 'This replaces the live database and uploads with %s. Type yes to continue: ' "$dir"
read -r answer
[ "$answer" = "yes" ] || { echo "cancelled"; exit 1; }

name="$(basename "$dir")"

docker compose stop web
# Bring the site back up even if a step below fails.
trap 'docker compose start web' EXIT
docker compose exec -T db sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$dir/db.dump"
# The web image has tar and mounts both upload volumes read-write. It runs
# as root here because backups are readable by root only.
docker compose run --rm --no-deps --user root -v "$(cd "$dir" && pwd):/restore:ro" --entrypoint sh web -c '
    set -e
    for v in media private_media; do
        find /app/$v -mindepth 1 -delete
        tar -xzf /restore/$v.tar.gz -C /app
        chown -R wagtail:wagtail /app/$v
    done
'
echo "restored $name"
