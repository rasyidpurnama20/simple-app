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
RUN groupadd --gid 20001 obe && useradd --uid 20001 --gid obe --no-create-home --shell /usr/sbin/nologin obe
COPY pyproject.toml ./
COPY requirements ./requirements
COPY config ./config
COPY obe ./obe
RUN pip install --upgrade pip && pip install .
COPY . .
COPY scripts/entrypoint.sh /usr/local/bin/obe-entrypoint
COPY --from=assets /build/static/vendor ./static/vendor
RUN sed -i 's/\r$//' /usr/local/bin/obe-entrypoint \
    && chmod 0755 /usr/local/bin/obe-entrypoint \
    && test "$(head -n 1 /usr/local/bin/obe-entrypoint)" = '#!/bin/sh' \
    && mkdir -p /app/var/evidence /app/var/uploads /app/staticfiles \
    && chown -R obe:obe /app
USER obe
RUN python manage.py collectstatic --noinput --settings=config.settings.local
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=3)"
ENTRYPOINT ["/usr/local/bin/obe-entrypoint"]
CMD ["web"]
