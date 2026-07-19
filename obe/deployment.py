from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DIGEST = re.compile(r"^[^\s]+@sha256:[0-9a-f]{64}$")
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._-]+$")
REQUIRED_IMAGES = {
    "OBE_IMAGE",
    "POSTGRES_IMAGE",
    "VALKEY_IMAGE",
    "RABBITMQ_IMAGE",
    "CLAMAV_IMAGE",
    "NGINX_IMAGE",
}
RESTORE_COMPONENTS = {
    "database": "backups",
    "evidence": "evidence",
    "queue": "queue",
    "cache": "cache",
    "observability": "observability",
    "config": "config",
}


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    environment: tuple[tuple[str, str], ...] = ()


def validate_image_digest(reference: str) -> bool:
    return bool(DIGEST.fullmatch(reference))


def load_environment_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or not name.strip():
            raise ValueError(f"Baris environment tidak valid di {path.name}")
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def validate_deployment_environment(environ: Mapping[str, str]) -> None:
    invalid = sorted(
        name for name in REQUIRED_IMAGES if not validate_image_digest(environ.get(name, ""))
    )
    if invalid:
        raise ValueError("Image wajib dipin dengan digest immutable: " + ", ".join(invalid))
    for name in ("OBE_SECRET_DIR", "OBE_ENV_FILE", "OBE_DATA_ROOT"):
        value = environ.get(name, "")
        if not value or not Path(value).is_absolute():
            raise ValueError(f"{name} wajib berupa path absolut")


def operation_plan(
    action: str,
    *,
    compose_file: Path,
    data_root: Path,
    image: str = "",
    component: str = "",
    snapshot: str = "latest",
    secret_type: str = "",
    secret_directory: Path | None = None,
    base_url: str = "https://127.0.0.1",
) -> tuple[Command, ...]:
    compose = ("docker", "compose", "-f", str(compose_file))
    if action == "deploy":
        return (
            Command((*compose, "pull")),
            Command((*compose, "up", "-d", "--remove-orphans", "--wait")),
        )
    if action == "migrate":
        return (Command((*compose, "run", "--rm", "migrate")),)
    if action == "rollback":
        if not validate_image_digest(image):
            raise ValueError("Rollback membutuhkan OBE_IMAGE dengan digest immutable")
        return (
            Command(
                (*compose, "up", "-d", "--no-deps", "--force-recreate", "web", "worker", "beat"),
                (("OBE_IMAGE", image),),
            ),
        )
    if action == "restore":
        if component not in RESTORE_COMPONENTS:
            raise ValueError("Komponen restore tidak dikenal")
        if not SAFE_IDENTIFIER.fullmatch(snapshot):
            raise ValueError("Snapshot restore tidak valid")
        include = data_root / RESTORE_COMPONENTS[component]
        commands = [
            Command((*compose, "stop", "web", "worker", "beat")),
            Command(("restic", "restore", snapshot, "--target", "/", "--include", str(include))),
        ]
        if component == "database":
            commands.append(
                Command(
                    (
                        *compose,
                        "exec",
                        "-T",
                        "database",
                        "pg_restore",
                        "--clean",
                        "--if-exists",
                        "-U",
                        "obe",
                        "-d",
                        "obe",
                        "/backups/database.dump",
                    )
                )
            )
        commands.append(Command((*compose, "up", "-d", "--wait")))
        return tuple(commands)
    if action == "rotate-secret":
        if secret_directory is None or not secret_directory.is_absolute():
            raise ValueError("Direktori secret wajib absolut")
        return (
            Command(
                (
                    "python",
                    "-m",
                    "scripts.rotate_secret",
                    secret_type,
                    "--directory",
                    str(secret_directory),
                )
            ),
        )
    if action == "smoke-test":
        return (Command(("python", "scripts/smoke_test.py", "--base-url", base_url)),)
    raise ValueError(f"Operasi tidak dikenal: {action}")
