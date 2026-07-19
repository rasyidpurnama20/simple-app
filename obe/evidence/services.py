from __future__ import annotations

import hashlib
import os
import socket
import struct
import uuid
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone

from obe.evidence.models import EvidenceRecord
from obe.identity.services import can
from obe.shared.models import FileManifest
from obe.shared.security import isolated_upload_name
from obe.shared.services import ActorContext, record_change
from obe.shared.telemetry import record_file_access, span

ALLOWED_MIME = {"application/pdf", "image/png", "image/jpeg", "text/csv"}
MAX_SIZE = 25 * 1024 * 1024
DOWNLOAD_SALT = "obe.evidence.download.v1"
TRANSITIONS = {
    EvidenceRecord.Status.DRAFT: {EvidenceRecord.Status.SUBMITTED},
    EvidenceRecord.Status.SUBMITTED: {
        EvidenceRecord.Status.VERIFIED,
        EvidenceRecord.Status.REJECTED,
    },
    EvidenceRecord.Status.REJECTED: {EvidenceRecord.Status.DRAFT},
    EvidenceRecord.Status.VERIFIED: {
        EvidenceRecord.Status.SUPERSEDED,
        EvidenceRecord.Status.ARCHIVED,
    },
    EvidenceRecord.Status.SUPERSEDED: {EvidenceRecord.Status.ARCHIVED},
    EvidenceRecord.Status.ARCHIVED: set(),
}


def _digest_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _prepare_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def _validate_file_signature(path: Path, mime_type: str) -> None:
    with path.open("rb") as stream:
        header = stream.read(16)
    signatures = {
        "application/pdf": (b"%PDF-",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/jpeg": (b"\xff\xd8\xff",),
    }
    expected = signatures.get(mime_type)
    if expected and not any(header.startswith(signature) for signature in expected):
        raise ValidationError("Signature file tidak cocok dengan MIME type")
    if mime_type == "text/csv" and (b"\x00" in header or not header):
        raise ValidationError("Konten CSV tidak aman")


def _clamav_scan(path: Path) -> str:
    with socket.create_connection(
        (settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=10
    ) as client:
        client.sendall(b"zINSTREAM\0")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(64 * 1024), b""):
                client.sendall(struct.pack("!I", len(chunk)))
                client.sendall(chunk)
        client.sendall(struct.pack("!I", 0))
        response = client.recv(4096).decode("utf-8", errors="replace").strip("\0\r\n")
    if response.endswith(" OK"):
        return response
    if " FOUND" in response:
        raise ValidationError("Berkas ditolak oleh antivirus")
    raise ValidationError("Antivirus tidak memberikan hasil valid")


def _lock_owner_quota(owner_id: str) -> None:
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [owner_id])


@transaction.atomic
def store(
    *,
    uploaded,
    owner_id: str,
    academic_object: str,
    classification: str,
    period: str = "",
    version: int = 1,
) -> EvidenceRecord:
    if uploaded.size <= 0 or uploaded.size > MAX_SIZE:
        raise ValidationError("Ukuran bukti harus 1 byte sampai 25 MiB")
    if uploaded.content_type not in ALLOWED_MIME:
        raise ValidationError("Tipe file tidak diizinkan")
    try:
        original_name = isolated_upload_name(
            uploaded.name,
            allowed_extensions={".pdf", ".png", ".jpg", ".jpeg", ".csv"},
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if classification not in FileManifest.Classification.values:
        raise ValidationError("Klasifikasi bukti tidak valid")
    if version < 1:
        raise ValidationError("Versi bukti minimal 1")
    object_type, separator, object_id = academic_object.partition(":")
    if not separator or not object_type or not object_id:
        raise ValidationError("Objek akademik harus berformat type:id")

    _lock_owner_quota(owner_id)
    used = FileManifest.objects.filter(owner_id=owner_id).aggregate(total=Sum("size"))["total"] or 0
    if used + uploaded.size > settings.EVIDENCE_OWNER_QUOTA_BYTES:
        raise ValidationError("Quota bukti pemilik terlampaui")

    root = Path(settings.EVIDENCE_ROOT).resolve()
    staging = root / ".staging"
    _prepare_private_directory(root)
    _prepare_private_directory(staging)
    staged = staging / str(uuid.uuid4())
    try:
        digest = hashlib.sha256()
        written = 0
        with staged.open("xb") as handle:
            staged.chmod(0o600)
            for chunk in uploaded.chunks():
                digest.update(chunk)
                written += len(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if written != uploaded.size:
            raise ValidationError("Ukuran upload tidak cocok dengan byte yang diterima")
        _validate_file_signature(staged, uploaded.content_type)

        sha = digest.hexdigest()
        scan_status = FileManifest.ScanStatus.SKIPPED
        scanner_signature = ""
        scanned_at = None
        if settings.EVIDENCE_ANTIVIRUS_REQUIRED:
            scanner_signature = _clamav_scan(staged)[:160]
            scan_status = FileManifest.ScanStatus.CLEAN
            scanned_at = timezone.now()

        target = root / sha[:2] / sha[2:4] / sha
        _prepare_private_directory(root / sha[:2])
        _prepare_private_directory(target.parent)
        try:
            os.link(staged, target)
            target.chmod(0o600)
        except FileExistsError:
            existing_sha, existing_size = _digest_file(target)
            if existing_sha != sha or existing_size != written:
                raise ValidationError("Content-addressed file yang ada gagal verifikasi") from None

        manifest = FileManifest.objects.create(
            sha256=sha,
            size=written,
            mime_type=uploaded.content_type,
            owner_id=owner_id,
            academic_object=academic_object,
            period=period,
            version=version,
            classification=classification,
            original_filename=original_name,
            content_path=str(target.relative_to(root)),
            scan_status=scan_status,
            scanner_signature=scanner_signature,
            scanned_at=scanned_at,
        )
        record = EvidenceRecord.objects.create(
            manifest=manifest,
            object_type=object_type,
            object_id=object_id,
        )
        transaction.on_commit(
            lambda: record_file_access(classification=classification, outcome="stored")
        )
        return record
    finally:
        staged.unlink(missing_ok=True)


def verify_integrity(record: EvidenceRecord) -> bool:
    with span("obe.evidence.verify", {"classification": record.manifest.classification}):
        root = Path(settings.EVIDENCE_ROOT).resolve()
        target = (root / record.manifest.content_path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            record_file_access(classification=record.manifest.classification, outcome="missing")
            return False
        digest, size = _digest_file(target)
        valid = digest == record.manifest.sha256 and size == record.manifest.size
        record_file_access(
            classification=record.manifest.classification,
            outcome="verified" if valid else "tamper",
        )
        return valid


@transaction.atomic
def transition(
    record: EvidenceRecord,
    *,
    target_status: str,
    actor_id: str,
    rejection_reason: str = "",
) -> EvidenceRecord:
    locked = EvidenceRecord.objects.select_for_update().get(pk=record.pk)
    if target_status not in TRANSITIONS[locked.status]:
        raise ValidationError(f"Transisi {locked.status} → {target_status} tidak diizinkan")
    if target_status == EvidenceRecord.Status.VERIFIED:
        if not verify_integrity(locked):
            raise ValidationError("Bukti gagal verifikasi checksum")
        locked.verified_by_id = actor_id
        locked.verified_at = timezone.now()
    if target_status == EvidenceRecord.Status.REJECTED:
        if not rejection_reason.strip():
            raise ValidationError("Alasan penolakan wajib diisi")
        locked.rejection_reason = rejection_reason.strip()
    locked.status = target_status
    locked.save()
    return locked


def can_access(user, record: EvidenceRecord) -> bool:
    if not user.is_authenticated:
        return False
    owner_match = record.manifest.owner_id in {str(user.pk), user.get_username()}
    scope = {
        "scope_type": record.object_type,
        "scope_id": record.object_id,
        "period": record.manifest.period,
        "owner_id": record.manifest.owner_id,
    }
    return (
        owner_match
        or can(user, "evidence.download", **scope)
        or can(user, "evidence.verify", **scope)
    )


def issue_download_token(record: EvidenceRecord, user) -> str:
    if not can_access(user, record):
        _audit_access(record, user, "denied")
        raise PermissionDenied("Akses bukti ditolak")
    return signing.dumps(
        {
            "evidence_id": str(record.public_id),
            "user_id": str(user.pk),
            "sha256": record.manifest.sha256,
        },
        salt=DOWNLOAD_SALT,
        compress=True,
    )


def resolve_download(token: str, user, *, max_age: int | None = None) -> EvidenceRecord:
    age = settings.EVIDENCE_DOWNLOAD_TTL_SECONDS if max_age is None else max_age
    try:
        payload = signing.loads(token, salt=DOWNLOAD_SALT, max_age=age)
        record = EvidenceRecord.objects.select_related("manifest").get(
            public_id=payload["evidence_id"]
        )
    except (signing.BadSignature, KeyError, EvidenceRecord.DoesNotExist) as exc:
        raise PermissionDenied("Token bukti tidak valid atau kedaluwarsa") from exc
    if payload["user_id"] != str(user.pk) or payload["sha256"] != record.manifest.sha256:
        _audit_access(record, user, "denied")
        raise PermissionDenied("Token bukti tidak sesuai pengguna")
    if not can_access(user, record) or not verify_integrity(record):
        _audit_access(record, user, "denied")
        raise PermissionDenied("Bukti tidak tersedia atau gagal verifikasi")
    _audit_access(record, user, "success")
    return record


def _audit_access(record: EvidenceRecord, user, outcome: str) -> None:
    record_file_access(classification=record.manifest.classification, outcome=outcome)
    record_change(
        actor=ActorContext(
            str(getattr(user, "pk", "")), getattr(user, "get_username", lambda: "")()
        ),
        action="evidence.download",
        object_type="evidence",
        object_id=str(record.public_id),
        summary=f"Evidence download {outcome}",
        after={"outcome": outcome, "sha256": record.manifest.sha256},
    )
