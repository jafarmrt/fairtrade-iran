#!/bin/sh
# Refresh the list of Parspack CDN addresses that nginx trusts (docker-compose.cdn.yml).
# Parspack publishes it at https://parspack.com/cdnips.txt and may change it.
# Run from the project folder, then restart nginx:
#
#   sh deploy/cdn/update-ips.sh && docker compose restart nginx
#
set -eu
cd "$(dirname "$0")"
URL="${CDN_IPS_URL:-https://parspack.com/cdnips.txt}"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl -fsS --max-time 30 "$URL" | tr -d '\r' | grep -E '^[0-9]{1,3}(\.[0-9]{1,3}){3}(/[0-9]{1,2})?$' > "$tmp" || true
if [ ! -s "$tmp" ]; then
    echo "Could not read $URL; the current list is kept." >&2
    exit 1
fi
{
    echo "# Parspack CDN addresses (from $URL, $(date -u +%Y-%m-%d)). Made by update-ips.sh; do not edit."
    sed 's/.*/set_real_ip_from &;/' "$tmp"
} > real-ip.conf
{
    echo "# Parspack CDN addresses (from $URL, $(date -u +%Y-%m-%d)). Made by update-ips.sh; do not edit."
    sed 's/.*/& 1;/' "$tmp"
} > cdn-ips.geo
echo "$(wc -l < "$tmp") Parspack CDN ranges written to deploy/cdn/."
