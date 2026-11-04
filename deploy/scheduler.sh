#!/bin/sh
# Jobs of the site. Runs inside the "scheduler" service of docker-compose.yml
# (same image as the site): the daily jobs once a day at $DAILY_JOBS_TIME, and
# every $PUBLISH_EVERY_MINUTES minutes the pages and documents editors scheduled
# in the admin ("تعیین زمان‌بندی"), which Wagtail only publishes when asked to.
#
#   scheduler.sh        loop forever
#   scheduler.sh now    run the jobs once and exit
set -u

DAILY_JOBS_TIME="${DAILY_JOBS_TIME:-08:00}"
PUBLISH_EVERY_MINUTES="${PUBLISH_EVERY_MINUTES:-10}"

publish_scheduled() {
    python manage.py publish_scheduled >/dev/null || echo "[scheduler] publish_scheduled FAILED"
}

run_jobs() {
    echo "[scheduler] $(date '+%Y-%m-%d %H:%M'): membership_reminders"
    python manage.py membership_reminders || echo "[scheduler] membership_reminders FAILED"
    echo "[scheduler] $(date '+%Y-%m-%d %H:%M'): membership_standing"
    python manage.py membership_standing || echo "[scheduler] membership_standing FAILED"
    echo "[scheduler] $(date '+%Y-%m-%d %H:%M'): assembly_daily"
    python manage.py assembly_daily || echo "[scheduler] assembly_daily FAILED"
    echo "[scheduler] $(date '+%Y-%m-%d %H:%M'): shop_daily"
    python manage.py shop_daily || echo "[scheduler] shop_daily FAILED"
    # Signed-out visitors' sessions (carts, order look-ups) would otherwise pile up in the database.
    python manage.py clearsessions || echo "[scheduler] clearsessions FAILED"
}

if [ "${1:-}" = "now" ]; then
    publish_scheduled
    run_jobs
    exit 0
fi

echo "[scheduler] daily jobs at $DAILY_JOBS_TIME ($(date +%Z)), scheduled publishing every $PUBLISH_EVERY_MINUTES minutes"
# Start counting from today, so a restart in the afternoon does not resend
# today's reminders.
last_run=""
if [ "$(date +%H:%M)" \> "$DAILY_JOBS_TIME" ]; then
    last_run="$(date +%Y-%m-%d)"
fi
minutes=0
while :; do
    if [ $((minutes % PUBLISH_EVERY_MINUTES)) -eq 0 ]; then
        publish_scheduled
    fi
    minutes=$((minutes + 1))
    now="$(date +%H:%M)"
    today="$(date +%Y-%m-%d)"
    if [ "$today" != "$last_run" ] && { [ "$now" = "$DAILY_JOBS_TIME" ] || [ "$now" \> "$DAILY_JOBS_TIME" ]; }; then
        last_run="$today"
        run_jobs
    fi
    sleep 60
done
