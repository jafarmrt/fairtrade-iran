#!/bin/sh
# Get the first Let's Encrypt certificate. Run once on the server, from the
# project folder, after the site already answers on http://<domain>/ :
#
#   ./deploy/init-https.sh admin@example.ir example.ir www.example.ir
#
# Then add this line to .env and restart:
#   COMPOSE_FILE=docker-compose.yml:docker-compose.https.yml
#   docker compose up -d
set -eu

email="${1:?usage: deploy/init-https.sh <email> <domain> [more domains...]}"
shift
[ $# -ge 1 ] || { echo "give at least one domain"; exit 1; }

domains=""
for d in "$@"; do domains="$domains -d $d"; done

# The plain-HTTP nginx must be running to answer the domain check.
docker compose -f docker-compose.yml up -d nginx

# shellcheck disable=SC2086
docker compose -f docker-compose.yml run --rm certbot certonly \
    --webroot -w /var/www/certbot \
    --cert-name site $domains \
    --email "$email" --agree-tos --no-eff-email --non-interactive

echo
echo "Certificate saved. Now add to .env:"
echo "  COMPOSE_FILE=docker-compose.yml:docker-compose.https.yml"
echo "and run: docker compose up -d"
