from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

ALLOWED_PROFILES = {"local", "test", "staging", "production", "exam-edge"}
STRICT_PROFILES = {"staging", "production", "exam-edge"}
PLACEHOLDERS = {
    "",
    "change-me",
    "changeme",
    "example",
    "password",
    "secret",
    "unsafe-local-only",
    "local-only-change-me",
}
ROTATION_POLICIES = {
    "OBE_SECRET_KEY": 90,
    "DATABASE_PASSWORD": 90,
    "LITELLM_API_KEY": 60,
    "OBE_EXAM_SIGNING_KEY": 90,
    "OBE_EXAM_SYNC_TOKEN": 30,
}


def secret_value(name: str, default: str = "", environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    direct = source.get(name, "")
    file_name = source.get(f"{name}_FILE", "")
    if direct and file_name:
        raise ImproperlyConfigured(f"Gunakan hanya {name} atau {name}_FILE, bukan keduanya")
    if file_name:
        path = Path(file_name)
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ImproperlyConfigured(f"Tidak dapat membaca {name}_FILE") from exc
        if not value:
            raise ImproperlyConfigured(f"{name}_FILE kosong")
        return value
    return direct or default


def secret_values(name: str, environ: Mapping[str, str] | None = None) -> list[str]:
    value = secret_value(name, environ=environ)
    return [item.strip() for item in value.splitlines() if item.strip()]


def requested_profile(environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    configured = source.get("OBE_ENV", "").strip()
    if configured:
        return configured
    settings_module = source.get("DJANGO_SETTINGS_MODULE", "")
    return "test" if settings_module.endswith(".test") else "local"


def _valid_url(value: str, *, schemes: set[str]) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in schemes and bool(parsed.hostname)


def _require_secret(name: str, value: str, minimum_length: int) -> None:
    normalized = value.strip().lower()
    if normalized in PLACEHOLDERS or len(value) < minimum_length:
        raise ImproperlyConfigured(
            f"{name} wajib berupa rahasia kuat (minimal {minimum_length} karakter)"
        )


def _parse_rotated_at(name: str, raw: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name}_ROTATED_AT harus berformat ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ImproperlyConfigured(f"{name}_ROTATED_AT harus menyertakan zona waktu")
    return parsed.astimezone(UTC)


def validate_runtime_configuration(
    namespace: Mapping[str, Any],
    expected_profile: str,
    *,
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> None:
    source = os.environ if environ is None else environ
    if expected_profile not in ALLOWED_PROFILES:
        raise ImproperlyConfigured(f"Profil lingkungan tidak dikenal: {expected_profile}")
    actual = str(namespace.get("OBE_ENV", ""))
    if actual != expected_profile:
        raise ImproperlyConfigured(
            f"Konfigurasi silang ditolak: OBE_ENV={actual!r}, profil={expected_profile!r}"
        )
    configured_profile = source.get("OBE_ENV", "").strip()
    if configured_profile and configured_profile != expected_profile:
        raise ImproperlyConfigured(
            f"Konfigurasi silang ditolak: OBE_ENV={configured_profile!r}, "
            f"profil={expected_profile!r}"
        )
    if expected_profile not in STRICT_PROFILES:
        return
    if source.get("OBE_ENV") != expected_profile:
        raise ImproperlyConfigured(f"OBE_ENV wajib eksplisit bernilai {expected_profile}")
    if namespace.get("DEBUG") is not False or namespace.get("SECURE_SSL_REDIRECT") is not True:
        raise ImproperlyConfigured("Mode keamanan lingkungan terkelola tidak valid")
    if (
        namespace.get("SESSION_COOKIE_SECURE") is not True
        or namespace.get("CSRF_COOKIE_SECURE") is not True
    ):
        raise ImproperlyConfigured("Cookie terkelola wajib secure")

    hosts = namespace.get("ALLOWED_HOSTS", [])
    if not hosts or any(host in {"*", "localhost", "127.0.0.1"} for host in hosts):
        raise ImproperlyConfigured(
            "OBE_ALLOWED_HOSTS harus berisi hostname terkelola yang spesifik"
        )
    csrf_origins = namespace.get("CSRF_TRUSTED_ORIGINS", [])
    if not csrf_origins or any(not str(origin).startswith("https://") for origin in csrf_origins):
        raise ImproperlyConfigured("CSRF trusted origins wajib eksplisit dan menggunakan HTTPS")
    try:
        admin_networks = [
            ipaddress.ip_network(value) for value in namespace.get("OBE_ADMIN_NETWORKS", [])
        ]
    except ValueError as exc:
        raise ImproperlyConfigured("OBE_ADMIN_NETWORKS tidak valid") from exc
    if not admin_networks or any(
        network.prefixlen == 0 or network.is_loopback for network in admin_networks
    ):
        raise ImproperlyConfigured("Admin wajib dibatasi ke jaringan VPN/allowlist")
    if not 3 <= int(namespace.get("OBE_LOGIN_LOCK_THRESHOLD", 0)) <= 10:
        raise ImproperlyConfigured("Threshold account lock harus 3–10")
    if not 300 <= int(namespace.get("OBE_LOGIN_LOCK_SECONDS", 0)) <= 86_400:
        raise ImproperlyConfigured("Durasi account lock harus 300–86400 detik")

    database = namespace.get("DATABASES", {}).get("default", {})
    if database.get("ENGINE") != "django.db.backends.postgresql":
        raise ImproperlyConfigured("Lingkungan terkelola wajib menggunakan PostgreSQL")
    database_password = str(database.get("PASSWORD", ""))
    _require_secret("DATABASE_PASSWORD", database_password, 12)
    _require_secret("OBE_SECRET_KEY", str(namespace.get("SECRET_KEY", "")), 50)
    for fallback in namespace.get("SECRET_KEY_FALLBACKS", []):
        _require_secret("OBE_SECRET_KEY_FALLBACKS", str(fallback), 50)
    if not 0 <= int(database.get("CONN_MAX_AGE", -1)) <= 600:
        raise ImproperlyConfigured("OBE_DB_CONN_MAX_AGE harus berada pada rentang 0–600 detik")
    if not 1 <= int(namespace.get("OBE_DB_CONNECTION_LIMIT", 0)) <= 1_000:
        raise ImproperlyConfigured("OBE_DB_CONNECTION_LIMIT harus berada pada rentang 1–1000")
    evidence_root = Path(namespace.get("EVIDENCE_ROOT", ""))
    if not evidence_root.is_absolute():
        raise ImproperlyConfigured("EVIDENCE_ROOT wajib berupa path absolut")
    if namespace.get("EVIDENCE_ANTIVIRUS_REQUIRED"):
        clamav_host = str(namespace.get("CLAMAV_HOST", ""))
        clamav_port = int(namespace.get("CLAMAV_PORT", 0))
        if not clamav_host or not 1 <= clamav_port <= 65535:
            raise ImproperlyConfigured("Endpoint ClamAV tidak valid")

    broker_url = str(namespace.get("CELERY_BROKER_URL", ""))
    isolated_memory_broker = expected_profile == "exam-edge" and broker_url == "memory://"
    if not isolated_memory_broker and not _valid_url(
        broker_url, schemes={"redis", "rediss", "amqp", "amqps"}
    ):
        raise ImproperlyConfigured("CELERY_BROKER_URL tidak valid untuk lingkungan terkelola")
    if not isolated_memory_broker and urlparse(broker_url).scheme not in {"amqp", "amqps"}:
        raise ImproperlyConfigured("Lingkungan terkelola wajib menggunakan RabbitMQ")
    cache_url = str(namespace.get("CACHE_URL", ""))
    result_backend = str(namespace.get("CELERY_RESULT_BACKEND", ""))
    if not _valid_url(cache_url, schemes={"redis", "rediss"}):
        raise ImproperlyConfigured("CACHE_URL terkelola wajib menggunakan Valkey/Redis protocol")
    if not _valid_url(result_backend, schemes={"redis", "rediss"}):
        raise ImproperlyConfigured("CELERY_RESULT_BACKEND wajib menggunakan short-lived Valkey")
    queue_names = {queue.name for queue in namespace.get("CELERY_TASK_QUEUES", ())}
    required_queues = {
        "interactive",
        "academic-critical",
        "ai",
        "reports",
        "imports",
        "notifications",
        "sync",
        "batch",
        "maintenance",
        "dead-letter",
    }
    if queue_names != required_queues:
        raise ImproperlyConfigured("Definisi antrean Celery tidak lengkap")
    if namespace.get("OBE_TELEMETRY_ENABLED") and not _valid_url(
        str(namespace.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")), schemes={"http", "https"}
    ):
        raise ImproperlyConfigured("Endpoint OTLP tidak valid")

    required_rotation = ["OBE_SECRET_KEY", "DATABASE_PASSWORD"]
    if bool(namespace.get("OBE_AI_ENABLED")):
        _require_secret("LITELLM_API_KEY", str(namespace.get("LITELLM_API_KEY", "")), 16)
        if not _valid_url(str(namespace.get("LITELLM_URL", "")), schemes={"http", "https"}):
            raise ImproperlyConfigured("LITELLM_URL tidak valid")
        required_rotation.append("LITELLM_API_KEY")
    if expected_profile == "exam-edge":
        _require_secret("OBE_EXAM_SIGNING_KEY", str(namespace.get("OBE_EXAM_SIGNING_KEY", "")), 32)
        for fallback in namespace.get("OBE_EXAM_SIGNING_KEY_FALLBACKS", []):
            _require_secret("OBE_EXAM_SIGNING_KEY_FALLBACKS", str(fallback), 32)
        _require_secret("OBE_EXAM_SYNC_TOKEN", str(namespace.get("OBE_EXAM_SYNC_TOKEN", "")), 32)
        required_rotation.extend(["OBE_EXAM_SIGNING_KEY", "OBE_EXAM_SYNC_TOKEN"])

    current = (now or datetime.now(UTC)).astimezone(UTC)
    for secret_name in required_rotation:
        variable = f"{secret_name}_ROTATED_AT"
        raw = source.get(variable, "")
        if not raw:
            raise ImproperlyConfigured(f"{variable} wajib diisi")
        rotated_at = _parse_rotated_at(secret_name, raw)
        if rotated_at > current + timedelta(minutes=5):
            raise ImproperlyConfigured(f"{variable} berada di masa depan")
        if current - rotated_at > timedelta(days=ROTATION_POLICIES[secret_name]):
            raise ImproperlyConfigured(f"{secret_name} kedaluwarsa dan wajib dirotasi")
