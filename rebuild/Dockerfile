FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 20001 stage0 \
    && useradd --uid 20001 --gid stage0 --no-create-home --shell /usr/sbin/nologin stage0

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY manage.py ./
COPY config ./config
COPY core ./core
COPY templates ./templates
COPY static ./static
COPY scripts/entrypoint.sh /usr/local/bin/obe-stage0-entrypoint

RUN sed -i 's/\r$//' /usr/local/bin/obe-stage0-entrypoint \
    && chmod 0755 /usr/local/bin/obe-stage0-entrypoint \
    && python manage.py collectstatic --noinput \
    && chown -R stage0:stage0 /app

USER stage0

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=2)"

ENTRYPOINT ["/usr/local/bin/obe-stage0-entrypoint"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
