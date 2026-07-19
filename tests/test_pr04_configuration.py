import logging
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.runtime import secret_value, validate_runtime_configuration
from obe.shared.queueing import build_task_queues
from obe.shared.redaction import (
    REDACTED,
    RedactingFormatter,
    SecretRedactionFilter,
    redact,
    register_sensitive_values,
)
from obe.shared.secret_rotation import revoke_previous, rotate_secret

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 19, tzinfo=UTC)


def managed_configuration(profile: str = "production") -> tuple[dict, dict[str, str]]:
    namespace = {
        "OBE_ENV": profile,
        "DEBUG": False,
        "SECURE_SSL_REDIRECT": True,
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
        "ALLOWED_HOSTS": [f"{profile}.example.invalid"],
        "CSRF_TRUSTED_ORIGINS": [f"https://{profile}.example.invalid"],
        "OBE_ADMIN_NETWORKS": ["10.70.0.0/24"],
        "OBE_LOGIN_LOCK_THRESHOLD": 5,
        "OBE_LOGIN_LOCK_SECONDS": 900,
        "DATABASES": {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "PASSWORD": "strong-database-password",
                "CONN_MAX_AGE": 60,
            }
        },
        "SECRET_KEY": "s" * 64,
        "CELERY_BROKER_URL": "amqps://broker.example.invalid/obe",
        "CELERY_RESULT_BACKEND": "rediss://cache.example.invalid/1",
        "CACHE_URL": "rediss://cache.example.invalid/0",
        "CELERY_TASK_QUEUES": build_task_queues(),
        "OBE_DB_CONNECTION_LIMIT": 20,
        "OBE_TELEMETRY_ENABLED": True,
        "OTEL_EXPORTER_OTLP_ENDPOINT": "https://telemetry.example.invalid",
        "OBE_AI_ENABLED": False,
        "LITELLM_API_KEY": "",
        "LITELLM_URL": "https://ai.example.invalid",
        "OBE_EXAM_SIGNING_KEY": "e" * 48,
        "OBE_EXAM_SYNC_TOKEN": "t" * 48,
        "EVIDENCE_ROOT": "/srv/obe/evidence",
        "EVIDENCE_ANTIVIRUS_REQUIRED": False,
    }
    environ = {
        "OBE_ENV": profile,
        "OBE_SECRET_KEY_ROTATED_AT": NOW.isoformat(),
        "DATABASE_PASSWORD_ROTATED_AT": NOW.isoformat(),
        "OBE_EXAM_SIGNING_KEY_ROTATED_AT": NOW.isoformat(),
        "OBE_EXAM_SYNC_TOKEN_ROTATED_AT": NOW.isoformat(),
    }
    return namespace, environ


def test_managed_environment_validates_at_startup():
    namespace, environ = managed_configuration()
    validate_runtime_configuration(namespace, "production", environ=environ, now=NOW)


def test_missing_and_expired_secrets_stop_startup():
    namespace, environ = managed_configuration()
    namespace["SECRET_KEY"] = ""
    with pytest.raises(ImproperlyConfigured, match="OBE_SECRET_KEY"):
        validate_runtime_configuration(namespace, "production", environ=environ, now=NOW)

    namespace["SECRET_KEY"] = "s" * 64
    environ["DATABASE_PASSWORD_ROTATED_AT"] = (NOW - timedelta(days=91)).isoformat()
    with pytest.raises(ImproperlyConfigured, match="kedaluwarsa"):
        validate_runtime_configuration(namespace, "production", environ=environ, now=NOW)


def test_cross_configuration_invalid_url_and_security_mode_are_rejected():
    namespace, environ = managed_configuration()
    namespace["OBE_ENV"] = "staging"
    with pytest.raises(ImproperlyConfigured, match="Konfigurasi silang"):
        validate_runtime_configuration(namespace, "production", environ=environ, now=NOW)

    namespace, environ = managed_configuration()
    environ["OBE_ENV"] = "staging"
    with pytest.raises(ImproperlyConfigured, match="Konfigurasi silang"):
        validate_runtime_configuration(namespace, "production", environ=environ, now=NOW)

    namespace, environ = managed_configuration()
    namespace["CELERY_BROKER_URL"] = "not-a-url"
    with pytest.raises(ImproperlyConfigured, match="CELERY_BROKER_URL"):
        validate_runtime_configuration(namespace, "production", environ=environ, now=NOW)

    namespace["CELERY_BROKER_URL"] = "amqps://broker.example.invalid/obe"
    namespace["DEBUG"] = True
    with pytest.raises(ImproperlyConfigured, match="Mode keamanan"):
        validate_runtime_configuration(namespace, "production", environ=environ, now=NOW)


def test_exam_edge_requires_rotatable_signing_and_sync_credentials():
    namespace, environ = managed_configuration("exam-edge")
    namespace["OBE_EXAM_SYNC_TOKEN"] = ""
    with pytest.raises(ImproperlyConfigured, match="OBE_EXAM_SYNC_TOKEN"):
        validate_runtime_configuration(namespace, "exam-edge", environ=environ, now=NOW)


def test_secret_file_is_exclusive_and_must_be_readable(tmp_path):
    secret_file = tmp_path / "secret"
    secret_file.write_text("from-file\n", encoding="utf-8")
    assert secret_value("TOKEN", environ={"TOKEN_FILE": str(secret_file)}) == "from-file"
    with pytest.raises(ImproperlyConfigured, match="bukan keduanya"):
        secret_value("TOKEN", environ={"TOKEN": "direct", "TOKEN_FILE": str(secret_file)})
    with pytest.raises(ImproperlyConfigured, match="Tidak dapat membaca"):
        secret_value("TOKEN", environ={"TOKEN_FILE": str(tmp_path / "missing")})


def test_secret_rotation_keeps_private_overlap_then_revokes(tmp_path):
    first = "a" * 48
    second = "b" * 48
    rotate_secret(tmp_path, "django-secret-key", value=first, rotated_at=NOW)
    metadata = rotate_secret(tmp_path, "django-secret-key", value=second, rotated_at=NOW)

    current = tmp_path / "obe_secret_key"
    previous = tmp_path / "obe_secret_key.previous"
    metadata_file = tmp_path / "obe_secret_key.metadata.json"
    assert current.read_text(encoding="utf-8").strip() == second
    assert previous.read_text(encoding="utf-8").strip() == first
    assert metadata["has_previous"] is True
    assert second not in metadata_file.read_text(encoding="utf-8")
    assert current.stat().st_mode & 0o777 == 0o600
    assert revoke_previous(tmp_path, "django-secret-key") is True
    assert revoke_previous(tmp_path, "django-secret-key") is False


def test_logs_and_nested_payloads_never_expose_secrets():
    known_value = "literal-sensitive-value"
    register_sensitive_values([known_value])
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SecretRedactionFilter())
    handler.setFormatter(RedactingFormatter("%(message)s"))
    logger = logging.getLogger("obe.tests.redaction")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    logger.info(
        "secret=%s database_url=postgresql://user:db-pass@db/obe Authorization: Bearer token123",
        known_value,
    )
    output = stream.getvalue()
    assert known_value not in output
    assert "db-pass" not in output
    assert "token123" not in output
    assert output.count(REDACTED) >= 3
    assert redact({"task": {"api_key": known_value}, "result": known_value}) == {
        "task": {"api_key": REDACTED},
        "result": REDACTED,
    }


def test_sops_and_environment_templates_contain_no_plaintext_secret_values():
    encrypted = (ROOT / "deploy/sops/secrets.example.enc.yaml").read_text(encoding="utf-8")
    for key in (
        "database_url",
        "django_secret_key",
        "litellm_api_key",
        "exam_signing_key",
        "exam_sync_token",
    ):
        assert f"{key}: ENC[" in encrypted

    for template in (ROOT / "deploy/env").glob("*.env.example"):
        content = template.read_text(encoding="utf-8")
        assert "OBE_SECRET_KEY=" not in content
        assert "LITELLM_API_KEY=" not in content
        assert "OBE_EXAM_SIGNING_KEY=" not in content
        assert "OBE_EXAM_SYNC_TOKEN=" not in content
        assert ".example.ac.id" not in content
        assert "/run/secrets/" not in content
        assert "2026-" not in content
