FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    DJANGO_SETTINGS_MODULE=fairtrade.settings.production

# Pillow and psycopg ship self-contained wheels, so no Debian packages are
# needed. That keeps the build working where Debian mirrors are slow or blocked.
RUN useradd --create-home wagtail

# Optional PyPI mirror for servers that cannot reach pypi.org, e.g.
#   docker compose build --build-arg PIP_INDEX_URL=https://mirror.example/simple
ARG PIP_INDEX_URL=https://pypi.org/simple

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt

COPY --chown=wagtail:wagtail . .
RUN mkdir -p /app/media /app/private_media /app/staticfiles \
    && chown -R wagtail:wagtail /app

USER wagtail

# collectstatic needs a SECRET_KEY to import settings; this one is never used at runtime.
RUN SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn fairtrade.wsgi:application --bind 0.0.0.0:${PORT} --workers 3 --timeout 60"]
