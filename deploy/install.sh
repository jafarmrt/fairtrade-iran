#!/usr/bin/env bash
# One-command installer for the Fair Trade House of Iran website on a fresh
# Ubuntu server (22.04 or 24.04). Run it as root from the project folder:
#
#   sudo ./deploy/install.sh
#
# It asks a few questions (domain, e-mail, SMTP), then:
#   1. installs Docker, git and a firewall, and sets the time zone
#   2. checks Docker Hub and PyPI, and sets up mirrors if they are blocked
#      (servers in Iran)
#   3. writes .env with random secrets (an existing .env is kept)
#   4. builds and starts the site, adds the starting content and an admin user
#   5. checks that the domain points to this server and turns on HTTPS
#
# It is safe to run again: finished steps are skipped. If the domain did not
# point here yet, fix DNS and run it again to get HTTPS.
#
# Answers can be given in advance as environment variables, for example:
#   sudo DOMAIN=fairtrade.ir ADMIN_EMAIL=info@fairtrade.ir ./deploy/install.sh --yes
# Variables: DOMAIN, WITH_WWW (1/0), ADMIN_EMAIL, ADMIN_USER, SMTP_HOST,
# SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, DOCKER_MIRROR, PIP_MIRROR.
# Advanced: SKIP_SYSTEM=1 (no apt/firewall), SKIP_HTTPS=1, BUILD=0 (use an
# image that is already built).

set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"
ASSUME_YES=0
[ "${1:-}" = "--yes" ] && ASSUME_YES=1

# Mirrors tried, in order, when Docker Hub is blocked (servers in Iran).
DEFAULT_DOCKER_MIRRORS="https://docker.arvancloud.ir https://docker.iranserver.com https://focker.ir"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[32m  ok:\033[0m %s\n' "$*"; }
warn() { printf '\033[33m  warning:\033[0m %s\n' "$*"; }
die()  { printf '\033[31m  error:\033[0m %s\n' "$*" >&2; exit 1; }

ask() {
    # ask VAR "Question" "default"
    local var="$1" question="$2" default="${3:-}" answer
    if [ -n "${!var:-}" ]; then return; fi
    if [ "$ASSUME_YES" = 1 ]; then printf -v "$var" '%s' "$default"; return; fi
    if [ -n "$default" ]; then
        read -r -p "  $question [$default]: " answer
    else
        read -r -p "  $question: " answer
    fi
    printf -v "$var" '%s' "${answer:-$default}"
}

ask_secret() {
    local var="$1" question="$2" answer
    if [ -n "${!var:-}" ] || [ "$ASSUME_YES" = 1 ]; then return; fi
    read -r -s -p "  $question: " answer
    echo
    printf -v "$var" '%s' "$answer"
}

env_get() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true; }

env_set() {
    # env_set KEY VALUE: replace the line, or append it
    local key="$1" value="$2"
    python3 - "$key" "$value" <<'PY'
import sys, re
key, value = sys.argv[1], sys.argv[2]
lines = open(".env").read().splitlines()
pattern = re.compile(r"^#?\s*" + re.escape(key) + "=")
for i, line in enumerate(lines):
    if pattern.match(line):
        lines[i] = f"{key}={value}"
        break
else:
    lines.append(f"{key}={value}")
open(".env", "w").write("\n".join(lines) + "\n")
PY
}

compose_http()  { docker compose -f docker-compose.yml "$@"; }

[ "$(id -u)" = 0 ] || die "run as root: sudo ./deploy/install.sh"
[ -f docker-compose.yml ] || die "run this from the project folder"

bold "Fair Trade House of Iran website: installer"

# ---------------------------------------------------------------- questions
step "Questions"
if [ -f .env ]; then
    ok ".env already exists; keeping its settings and secrets"
    DOMAIN="${DOMAIN:-$(env_get SITE_URL | sed -E 's#^https?://##; s#/.*$##')}"
    if [ -z "${WITH_WWW:-}" ]; then
        case ",$(env_get ALLOWED_HOSTS)," in *",www."*) WITH_WWW=1 ;; *) WITH_WWW=0 ;; esac
    fi
fi
ask DOMAIN "Domain name, without www (e.g. fairtrade.ir)" ""
[ -n "$DOMAIN" ] || die "a domain is needed"
DOMAIN="${DOMAIN#www.}"
ask WITH_WWW "Also serve www.$DOMAIN? (1 = yes, 0 = no)" "1"
ask ADMIN_EMAIL "Your e-mail (admin account and certificate expiry notices)" "admin@$DOMAIN"
ask ADMIN_USER "Admin username" "admin"

HOSTS="$DOMAIN"
[ "$WITH_WWW" = 1 ] && HOSTS="$DOMAIN www.$DOMAIN"

if [ ! -f .env ]; then
    echo "  Outgoing e-mail (SMTP). Leave the server empty to set it up later;"
    echo "  until then e-mails are only written to the site log."
    ask SMTP_HOST "SMTP server (e.g. mail.$DOMAIN)" ""
    if [ -n "$SMTP_HOST" ]; then
        ask SMTP_PORT "SMTP port" "587"
        ask SMTP_USER "SMTP username" "no-reply@$DOMAIN"
        ask_secret SMTP_PASSWORD "SMTP password"
        ask SMTP_FROM "Sender address" "${SMTP_USER:-no-reply@$DOMAIN}"
    fi
fi

# ---------------------------------------------------------------- system
if [ "${SKIP_SYSTEM:-0}" != 1 ]; then
    step "System packages, firewall and time zone"
    export DEBIAN_FRONTEND=noninteractive
    need=""
    command -v git >/dev/null || need="$need git"
    command -v curl >/dev/null || need="$need curl"
    command -v ufw >/dev/null || need="$need ufw"
    command -v openssl >/dev/null || need="$need openssl"
    command -v python3 >/dev/null || need="$need python3"
    command -v docker >/dev/null || need="$need docker.io"
    docker compose version >/dev/null 2>&1 || need="$need docker-compose-v2"
    if [ -n "$need" ]; then
        apt-get update -q
        # shellcheck disable=SC2086
        apt-get install -y -q $need
    fi
    ok "packages installed"
    systemctl enable --now docker >/dev/null 2>&1 || true
    ufw allow OpenSSH >/dev/null
    ufw allow 80/tcp >/dev/null
    ufw allow 443/tcp >/dev/null
    ufw --force enable >/dev/null
    ok "firewall: SSH, 80 and 443 open"
    timedatectl set-timezone Asia/Tehran 2>/dev/null || true
fi
docker info >/dev/null 2>&1 || die "Docker is not running (systemctl start docker)"
docker compose version >/dev/null 2>&1 || die "docker compose is missing (apt install docker-compose-v2)"

# ---------------------------------------------------------------- mirrors
step "Checking access to Docker Hub and PyPI"
needed_images="postgres:16-alpine nginx:1.27-alpine certbot/certbot:v3.1.0"
[ "${BUILD:-1}" != 0 ] && needed_images="$needed_images python:3.12-slim-bookworm"
missing_images=""
for img in $needed_images; do
    docker image inspect "$img" >/dev/null 2>&1 || missing_images="$missing_images $img"
done
if [ -z "$missing_images" ]; then
    ok "all base images are already on this server"
elif timeout 60 docker pull -q hello-world >/dev/null 2>&1; then
    ok "Docker Hub reachable"
else
    warn "Docker Hub is not reachable (normal on servers in Iran); trying mirrors"
    mirrors="${DOCKER_MIRROR:-$DEFAULT_DOCKER_MIRRORS}"
    found=""
    for m in $mirrors; do
        python3 - "$m" <<'PY'
import json, os, sys
path = "/etc/docker/daemon.json"
conf = json.load(open(path)) if os.path.exists(path) and os.path.getsize(path) else {}
conf["registry-mirrors"] = [sys.argv[1]]
json.dump(conf, open(path, "w"), indent=2)
PY
        systemctl restart docker 2>/dev/null || service docker restart
        sleep 3
        if timeout 90 docker pull -q hello-world >/dev/null 2>&1; then
            found="$m"
            break
        fi
        warn "mirror $m did not work"
    done
    [ -n "$found" ] || die "no Docker mirror worked. Ask your hosting company for one and run again with DOCKER_MIRROR=https://..."
    ok "using Docker mirror $found"
fi

if [ -z "${PIP_MIRROR:-}" ] && ! timeout 20 curl -sSf -o /dev/null https://pypi.org/simple/django/ 2>/dev/null; then
    warn "pypi.org is not reachable from this server."
    ask PIP_MIRROR "PyPI mirror address ending in /simple (ask your hosting company)" ""
fi

# ---------------------------------------------------------------- .env
step "Settings file (.env)"
if [ ! -f .env ]; then
    cp .env.example .env
    env_set SECRET_KEY "$(openssl rand -hex 40)"
    env_set POSTGRES_PASSWORD "$(openssl rand -hex 24)"
    env_set ALLOWED_HOSTS "$(echo "$HOSTS" | tr ' ' ',')"
    env_set CSRF_TRUSTED_ORIGINS "$(for h in $HOSTS; do printf 'https://%s,' "$h"; done | sed 's/,$//')"
    env_set SITE_URL "https://$DOMAIN"
    env_set USE_HTTPS 1
    if [ -n "${SMTP_HOST:-}" ]; then
        env_set EMAIL_HOST "$SMTP_HOST"
        env_set EMAIL_PORT "${SMTP_PORT:-587}"
        env_set EMAIL_HOST_USER "${SMTP_USER:-}"
        env_set EMAIL_HOST_PASSWORD "${SMTP_PASSWORD:-}"
        env_set DEFAULT_FROM_EMAIL "${SMTP_FROM:-no-reply@$DOMAIN}"
        [ "${SMTP_PORT:-587}" = 465 ] && env_set EMAIL_USE_TLS 0
    else
        env_set EMAIL_BACKEND django.core.mail.backends.console.EmailBackend
        env_set DEFAULT_FROM_EMAIL "no-reply@$DOMAIN"
    fi
    chmod 600 .env
    ok ".env written with new random secrets"
else
    ok ".env kept"
fi
[ -n "${PIP_MIRROR:-}" ] && env_set PIP_INDEX_URL "$PIP_MIRROR"
mkdir -p backups

# ---------------------------------------------------------------- start
step "Building and starting the site (the first build takes a few minutes)"
build_flag="--build"
[ "${BUILD:-1}" = 0 ] && build_flag="--no-build"
if [ -n "$(env_get COMPOSE_FILE)" ]; then
    docker compose up -d $build_flag --wait --wait-timeout 600
else
    compose_http up -d $build_flag --wait --wait-timeout 600
fi
ok "site is running"

step "Starting content"
compose_http exec -T web python manage.py seed_content >/tmp/fairtrade-seed.log 2>&1 \
    || { tail -20 /tmp/fairtrade-seed.log; die "seed_content failed (full log: /tmp/fairtrade-seed.log)"; }
ok "pages, groups, document collections and texts are in place"

step "Admin account"
ADMIN_PASSWORD=""
has_admin="$(compose_http exec -T web python manage.py shell -c \
    "from django.contrib.auth import get_user_model; print(get_user_model().objects.filter(is_superuser=True).exists())" | tail -1)"
if [ "$has_admin" = "True" ]; then
    ok "an admin account already exists"
else
    ADMIN_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)"
    compose_http exec -T \
        -e DJANGO_SUPERUSER_USERNAME="$ADMIN_USER" \
        -e DJANGO_SUPERUSER_EMAIL="$ADMIN_EMAIL" \
        -e DJANGO_SUPERUSER_PASSWORD="$ADMIN_PASSWORD" \
        web python manage.py createsuperuser --noinput >/dev/null
    umask 077
    printf 'Admin: https://%s/admin/\nUsername: %s\nPassword: %s\n' "$DOMAIN" "$ADMIN_USER" "$ADMIN_PASSWORD" > /root/fairtrade-admin.txt
    ok "admin '$ADMIN_USER' created (password saved in /root/fairtrade-admin.txt)"
fi

# ---------------------------------------------------------------- HTTPS
HTTPS_OK=0
if [ "${SKIP_HTTPS:-0}" = 1 ]; then
    warn "HTTPS skipped (SKIP_HTTPS=1)"
elif [ -n "$(env_get COMPOSE_FILE)" ]; then
    HTTPS_OK=1
    ok "HTTPS already set up"
else
    step "HTTPS certificate"
    token="check-$(openssl rand -hex 8)"
    compose_http run --rm --no-deps --entrypoint sh certbot -c \
        "mkdir -p /var/www/certbot/.well-known/acme-challenge && echo $token > /var/www/certbot/.well-known/acme-challenge/$token" >/dev/null 2>&1
    dns_ok=1
    for h in $HOSTS; do
        got="$(timeout 15 curl -s --noproxy '*' "http://$h/.well-known/acme-challenge/$token" || true)"
        if [ "$got" = "$token" ]; then
            ok "$h points to this server"
        else
            warn "$h does not reach this server yet (check its DNS A record)"
            dns_ok=0
        fi
    done
    compose_http run --rm --no-deps --entrypoint sh certbot -c "rm -f /var/www/certbot/.well-known/acme-challenge/$token" >/dev/null 2>&1 || true

    if [ "$dns_ok" = 1 ]; then
        # shellcheck disable=SC2086
        if ./deploy/init-https.sh "$ADMIN_EMAIL" $HOSTS >/tmp/fairtrade-https.log 2>&1; then
            env_set COMPOSE_FILE "docker-compose.yml:docker-compose.https.yml"
            docker compose up -d --wait --wait-timeout 300 >/dev/null
            HTTPS_OK=1
            ok "certificate issued; HTTPS is on and renews itself"
        else
            warn "Let's Encrypt refused the certificate. Details: /tmp/fairtrade-https.log"
            warn "This often happens during international internet disruptions. Run this installer again later."
        fi
    else
        warn "HTTPS not set up yet. Fix DNS, wait a little, then run: sudo ./deploy/install.sh"
    fi
fi

# ---------------------------------------------------------------- summary
step "Done"
if [ "$HTTPS_OK" = 1 ]; then
    echo "  Site:   https://$DOMAIN/fa/   and   https://$DOMAIN/en/"
    echo "  Admin:  https://$DOMAIN/admin/"
else
    echo "  Site (no HTTPS yet): http://$DOMAIN/fa/"
    echo "  The admin panel needs HTTPS; run this installer again once DNS is ready."
fi
if [ -n "$ADMIN_PASSWORD" ]; then
    echo "  Admin username: $ADMIN_USER"
    echo "  Admin password: $ADMIN_PASSWORD   (also in /root/fairtrade-admin.txt; change it after signing in)"
fi
[ -z "${SMTP_HOST:-}" ] && [ "$(env_get EMAIL_BACKEND)" = "django.core.mail.backends.console.EmailBackend" ] && \
    echo "  E-mail is not set up: fill in EMAIL_* in .env, delete the EMAIL_BACKEND line, then run: docker compose up -d"
echo "  Backups: daily into $PROJECT_DIR/backups. Copy them off this server regularly."
echo "  Updates: sudo ./deploy/update.sh"
echo "  Next: fill in Settings in the admin panel (docs/deploy-fa.md, section 8)."
