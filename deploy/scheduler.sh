#!/bin/sh
# Daily jobs of the site. Runs inside the "scheduler" service of
# docker-compose.yml (same image as the site), once a day at $DAILY_JOBS_TIME.
#
#   scheduler.sh        loop forever
#   scheduler.sh now    run the jobs once and exit
set -u

DAILY_JOBS_TIME="${DAILY_JOBS_TIME:-08:00}"

run_jobs() {
    echo "[scheduler] $(date '+%Y-%m-%d %H:%M'): membership_reminders"
    python manage.py membership_reminders || echo "[scheduler] membership_reminders FAILED"
    echo "[scheduler] $(date '+%Y-%m-%d %H:%M'): membership_standing"
    python manage.py membership_standing || echo "[scheduler] membership_standing FAILED"
    echo "[scheduler] $(date '+%Y-%m-%d %H:%M'): shop_daily"
    python manage.py shop_daily || echo "[scheduler] shop_daily FAILED"
}

if [ "${1:-}" = "now" ]; then
    run_jobs
    exit 0
fi

echo "[scheduler] daily jobs at $DAILY_JOBS_TIME ($(date +%Z))"
# Start counting from today, so a restart in the afternoon does not resend
# today's reminders.
last_run=""
if [ "$(date +%H:%M)" \> "$DAILY_JOBS_TIME" ]; then
    last_run="$(date +%Y-%m-%d)"
fi
while :; do
    now="$(date +%H:%M)"
    today="$(date +%Y-%m-%d)"
    if [ "$today" != "$last_run" ] && { [ "$now" = "$DAILY_JOBS_TIME" ] || [ "$now" \> "$DAILY_JOBS_TIME" ]; }; then
        last_run="$today"
        run_jobs
    fi
    sleep 60
done
