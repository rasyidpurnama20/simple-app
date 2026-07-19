from __future__ import annotations

import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path

SECRET_FILE_NAMES = {
    "database-password": "database_password",
    "django-secret-key": "obe_secret_key",
    "litellm-api-key": "litellm_api_key",
    "exam-signing-key": "obe_exam_signing_key",
    "exam-sync-token": "obe_exam_sync_token",
}


def _atomic_private_write(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def rotate_secret(
    secret_directory: Path,
    secret_type: str,
    *,
    value: str | None = None,
    rotated_at: datetime | None = None,
) -> dict[str, str | bool]:
    if secret_type not in SECRET_FILE_NAMES:
        raise ValueError(f"Jenis secret tidak didukung: {secret_type}")
    name = SECRET_FILE_NAMES[secret_type]
    current = secret_directory / name
    previous = secret_directory / f"{name}.previous"
    if current.exists():
        _atomic_private_write(previous, current.read_text(encoding="utf-8"))
    generated = value or secrets.token_urlsafe(48)
    if len(generated) < 32:
        raise ValueError("Secret baru minimal 32 karakter")
    _atomic_private_write(current, f"{generated.rstrip()}\n")
    timestamp = (rotated_at or datetime.now(UTC)).astimezone(UTC).isoformat()
    metadata: dict[str, str | bool] = {
        "secret_type": secret_type,
        "rotated_at": timestamp,
        "has_previous": previous.exists(),
    }
    _atomic_private_write(
        secret_directory / f"{name}.metadata.json",
        f"{json.dumps(metadata, sort_keys=True)}\n",
    )
    return metadata


def revoke_previous(secret_directory: Path, secret_type: str) -> bool:
    if secret_type not in SECRET_FILE_NAMES:
        raise ValueError(f"Jenis secret tidak didukung: {secret_type}")
    previous = secret_directory / f"{SECRET_FILE_NAMES[secret_type]}.previous"
    if not previous.exists():
        return False
    previous.unlink()
    return True
