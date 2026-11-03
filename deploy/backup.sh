#!/bin/sh
# Daily backup of the database and both upload volumes.
#
# Runs inside the "backup" service of docker-compose.yml, which mounts:
#   /data/media          public uploads (read-only)
#   /data/private_media  application documents and receipts (read-only)
#   /backups             ./backups on the server
#
#   backup.sh            loop forever, back up once a day at $BACKUP_TIME
#   backup.sh now        back up once and exit
#
# Each run writes /backups/<date-time>/ with db.dump, media.tar.gz and
# private_media.tar.gz, then deletes runs older than $BACKUP_KEEP_DAYS days.
set -eu

BACKUP_TIME="${BACKUP_TIME:-03:30}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

run_backup() {
    stamp="$(date +%Y-%m-%d_%H%M)"
    target="/backups/$stamp"
    tmp="/backups/.incomplete-$stamp"
    rm -rf "$tmp"
    mkdir -p "$tmp"

    echo "[backup] $stamp: database"
    pg_dump --format=custom --no-owner --file="$tmp/db.dump"

    echo "[backup] $stamp: media"
    tar -czf "$tmp/media.tar.gz" -C /data media

    echo "[backup] $stamp: private_media"
    tar -czf "$tmp/private_media.tar.gz" -C /data private_media

    # Only a complete run gets its final name, so a half-written backup is
    # never mistaken for a good one.
    mv "$tmp" "$target"
    chmod -R go-rwx "$target"
    echo "[backup] $stamp: done ($(du -sh "$target" | cut -f1))"

    find /backups -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +"$BACKUP_KEEP_DAYS" \
        -exec echo "[backup] removing old" {} \; -exec rm -rf {} +
}

if [ "${1:-}" = "now" ]; then
    run_backup
    exit 0
fi

echo "[backup] waiting; daily backup at $BACKUP_TIME ($(date +%Z)), keeping $BACKUP_KEEP_DAYS days"
last_run=""
while :; do
    now="$(date +%H:%M)"
    today="$(date +%Y-%m-%d)"
    if [ "$today" != "$last_run" ] && { [ "$now" = "$BACKUP_TIME" ] || [ "$now" \> "$BACKUP_TIME" ]; }; then
        last_run="$today"
        # A failed run is logged and retried the next day; the loop keeps going.
        run_backup || echo "[backup] FAILED, see the messages above"
    fi
    sleep 60
done
