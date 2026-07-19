FROM node:24-alpine AS assets
WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm install --ignore-scripts
COPY assets ./assets
COPY static ./static
COPY templates ./templates
COPY obe ./obe
COPY scripts ./scripts
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN addgroup --system obe && adduser --system --ingroup obe obe
COPY pyproject.toml ./
COPY requirements ./requirements
COPY config ./config
COPY obe ./obe
RUN pip install --upgrade pip && pip install .
COPY . .
COPY --from=assets /build/static/vendor ./static/vendor
RUN mkdir -p /app/var/evidence /app/var/uploads /app/staticfiles && chown -R obe:obe /app
USER obe
RUN python manage.py collectstatic --noinput --settings=config.settings.local
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=3)"
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--access-logfile", "-"]
