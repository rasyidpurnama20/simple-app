from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any


def _digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def create_inventory(root: Path) -> dict[str, Any]:
    resolved = root.resolve()
    files = []
    if resolved.exists():
        for path in sorted(resolved.rglob("*")):
            if not path.is_file() or ".staging" in path.parts:
                continue
            sha256, size = _digest(path)
            files.append({"path": str(path.relative_to(resolved)), "sha256": sha256, "size": size})
    return {"schema_version": "1.0", "files": files}


def verify_inventory(
    root: Path, inventory: dict[str, Any], *, selected_sha256: set[str] | None = None
) -> bool:
    resolved = root.resolve()
    for item in inventory.get("files", []):
        if selected_sha256 is not None and item["sha256"] not in selected_sha256:
            continue
        path = (resolved / item["path"]).resolve()
        if not path.is_relative_to(resolved) or not path.is_file():
            return False
        sha256, size = _digest(path)
        if sha256 != item["sha256"] or size != item["size"]:
            return False
    return True


def restore_inventory(
    snapshot_root: Path,
    target_root: Path,
    inventory: dict[str, Any],
    *,
    selected_sha256: set[str] | None = None,
) -> int:
    source_root = snapshot_root.resolve()
    destination_root = target_root.resolve()
    destination_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    restored = 0
    for item in inventory.get("files", []):
        if selected_sha256 is not None and item["sha256"] not in selected_sha256:
            continue
        source = (source_root / item["path"]).resolve()
        destination = (destination_root / item["path"]).resolve()
        if not source.is_relative_to(source_root) or not destination.is_relative_to(
            destination_root
        ):
            raise ValueError("Path inventory keluar dari root")
        if not source.is_file() or _digest(source) != (item["sha256"], item["size"]):
            raise ValueError("Snapshot evidence gagal verifikasi")
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.restore")
        try:
            shutil.copyfile(source, temporary)
            temporary.chmod(0o600)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        restored += 1
    if not verify_inventory(destination_root, inventory, selected_sha256=selected_sha256):
        raise ValueError("Checksum hasil restore tidak 100% cocok")
    return restored
