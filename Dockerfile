FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    DJANGO_SETTINGS_MODULE=fairtrade.settings.production

RUN apt-get update --yes --quiet && apt-get install --yes --quiet --no-install-recommends \
        libjpeg62-turbo zlib1g libwebp7 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home wagtail

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=wagtail:wagtail . .
RUN mkdir -p /app/media /app/private_media /app/staticfiles \
    && chown -R wagtail:wagtail /app

USER wagtail

# collectstatic needs a SECRET_KEY to import settings; this one is never used at runtime.
RUN SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn fairtrade.wsgi:application --bind 0.0.0.0:${PORT} --workers 3 --timeout 60"]
