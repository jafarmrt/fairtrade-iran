# Free test copy of the site on Hugging Face Spaces, with demo data.
# Copy this file and README.md (same folder) into a new Docker Space.
# Guide in Persian: docs/demo-fa.md. Not for the real site.
#
# The code is downloaded from GitHub (branch main) at build time; to pick up
# new changes, use "Factory rebuild" in the Space settings. The database
# (SQLite) and sample pictures are built into the image, so every restart
# begins from the same clean demo content.

FROM python:3.12-slim-bookworm

ARG REPO_TARBALL=https://github.com/jafarmrt/fairtrade-iran/archive/refs/heads/main.tar.gz

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    DJANGO_SETTINGS_MODULE=fairtrade.settings.production \
    DEMO_MODE=1 \
    DATABASE_URL=sqlite:////app/demo/demo.sqlite3 \
    PAYMENT_ALLOW_TEST_GATEWAY=1 \
    EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend \
    SMS_BACKEND=sms.backends.ConsoleBackend \
    WEB_CONCURRENCY=3

# Spaces run the container as uid 1000, which is this first user.
RUN useradd --create-home --uid 1000 wagtail

RUN python -c "import io, tarfile, urllib.request; \
tarfile.open(fileobj=io.BytesIO(urllib.request.urlopen('${REPO_TARBALL}').read())).extractall('/tmp/src')" \
    && mv /tmp/src/* /app && rm -rf /tmp/src

WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /app/media /app/private_media /app/staticfiles /app/demo \
    && chown -R wagtail:wagtail /app
USER wagtail

# Build-time only values: SECRET_KEY and DEMO_PASSWORD come from the Space's secrets at runtime.
RUN export SECRET_KEY=build-only ALLOWED_HOSTS=localhost \
    && python manage.py collectstatic --noinput \
    && python manage.py migrate --noinput \
    && DEMO_PASSWORD=build-only-placeholder python manage.py seed_demo

EXPOSE 7860
CMD ["sh", "-c", "python manage.py seed_demo --passwords-only && gunicorn fairtrade.wsgi:application --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY} --timeout 60"]
