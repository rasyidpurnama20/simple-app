from __future__ import annotations

import shutil
import time
from datetime import date
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, transaction
from django.db.models.deletion import ProtectedError
from django.urls import reverse

from obe.curriculum.models import Course, CurriculumVersion
from obe.deployment import (
    load_environment_file,
    operation_plan,
    validate_deployment_environment,
    validate_image_digest,
)
from obe.evidence.backup import create_inventory, restore_inventory, verify_inventory
from obe.evidence.models import EvidenceRecord
from obe.evidence.services import (
    issue_download_token,
    resolve_download,
    store,
    transition,
    verify_integrity,
)
from obe.shared.models import AuditEvent, FileManifest
from obe.shared.services import create_versioned, run_with_deadlock_retry, update_versioned

ROOT = Path(__file__).resolve().parents[1]
DIGEST = "a" * 64


def deployment_environment(tmp_path: Path) -> dict[str, str]:
    values = {
        name: f"registry.example/{name.lower()}@sha256:{DIGEST}"
        for name in (
            "OBE_IMAGE",
            "POSTGRES_IMAGE",
            "VALKEY_IMAGE",
            "RABBITMQ_IMAGE",
            "CLAMAV_IMAGE",
            "NGINX_IMAGE",
        )
    }
    values.update(
        {
            "OBE_SECRET_DIR": str(tmp_path / "secrets"),
            "OBE_ENV_FILE": str(tmp_path / "production.env"),
            "OBE_DATA_ROOT": str(tmp_path / "data"),
        }
    )
    return values


def uploaded(content: bytes = b"evidence", name: str = "evidence.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def test_pr05_has_separate_digest_pinned_compose_contracts_and_ansible():
    server = (ROOT / "deploy/server/compose.yml").read_text(encoding="utf-8")
    edge = (ROOT / "deploy/exam-edge/compose.yml").read_text(encoding="utf-8")
    ansible = (ROOT / "deploy/ansible/roles/obe/tasks/main.yml").read_text(encoding="utf-8")
    inventory = (ROOT / "deploy/ansible/inventory.example.yml").read_text(encoding="utf-8")
    backup = (ROOT / "deploy/ansible/roles/obe/templates/obe-backup.sh.j2").read_text(
        encoding="utf-8"
    )
    for compose in (server, edge):
        assert "${OBE_IMAGE:?" in compose
        assert "${POSTGRES_IMAGE:?" in compose
        assert "healthcheck:" in compose
        assert "resources:" in compose
        assert "restart:" in compose
    for component in ("database", "evidence", "queue", "observability", "config"):
        assert component in server or component in ansible
    for capability in ("ufw", "restic", "prometheus-node-exporter", "TLS", "scripts.obe_ops"):
        assert capability in ansible
    assert "pg_dump" in backup and "restic backup" in backup and "restic check" in backup
    assert ".example.invalid" in inventory and ".internal" not in inventory
    assert inventory.count("obe_deploy_enabled: false") == 2


def test_deployment_validation_and_operation_plans_are_deterministic(tmp_path):
    environment = deployment_environment(tmp_path)
    validate_deployment_environment(environment)
    assert validate_image_digest(environment["OBE_IMAGE"])
    with pytest.raises(ValueError, match="digest immutable"):
        validate_deployment_environment({**environment, "NGINX_IMAGE": "nginx:latest"})

    compose = ROOT / "deploy/server/compose.yml"
    first = operation_plan("deploy", compose_file=compose, data_root=tmp_path)
    assert first == operation_plan("deploy", compose_file=compose, data_root=tmp_path)
    assert first[-1].argv[-1] == "--wait"
    rollback = operation_plan(
        "rollback",
        compose_file=compose,
        data_root=tmp_path,
        image=environment["OBE_IMAGE"],
    )
    assert rollback[0].environment == (("OBE_IMAGE", environment["OBE_IMAGE"]),)
    restore = operation_plan(
        "restore",
        compose_file=compose,
        data_root=Path("/srv/obe"),
        component="database",
        snapshot="snapshot-1",
    )
    assert len(restore) == 4 and "pg_restore" in restore[2].argv
    env_file = tmp_path / "deployment.env"
    env_file.write_text(
        "# pinned\nOBE_IMAGE=registry/app@sha256:" + DIGEST + "\n", encoding="utf-8"
    )
    assert load_environment_file(env_file)["OBE_IMAGE"].endswith(DIGEST)


@pytest.mark.django_db
def test_maintenance_mode_and_query_budget_header(client, settings):
    settings.OBE_MAINTENANCE_MODE = True
    assert client.get(reverse("healthz")).status_code == 200
    response = client.get(reverse("readyz"))
    assert response.status_code == 503
    assert response["Retry-After"] == "300"
    settings.OBE_MAINTENANCE_MODE = False
    assert int(client.get(reverse("readyz"))["X-Query-Count"]) >= 1


@pytest.mark.django_db
def test_critical_read_p95_and_query_count_stay_within_baseline(client):
    durations = []
    query_counts = []
    for _ in range(20):
        started = time.perf_counter()
        response = client.get(reverse("readyz"))
        durations.append(time.perf_counter() - started)
        query_counts.append(int(response["X-Query-Count"]))
    p95 = sorted(durations)[18]
    assert p95 <= 2.5
    assert max(query_counts) <= 2


def test_database_connection_has_health_and_connection_limits(settings):
    database = settings.DATABASES["default"]
    assert database["CONN_HEALTH_CHECKS"] is True
    assert 0 <= database["CONN_MAX_AGE"] <= 600


@pytest.mark.django_db
def test_optimistic_lock_rejects_stale_write_and_records_actor():
    curriculum = create_versioned(
        CurriculumVersion,
        actor_id="operator-0",
        program_code="IF",
        name="Kurikulum",
        cohort_from=2026,
    )
    assert curriculum.created_by_actor_id == curriculum.updated_by_actor_id == "operator-0"
    updated = update_versioned(
        curriculum,
        expected_lock_version=0,
        actor_id="operator-1",
        changes={"name": "Kurikulum 2026"},
    )
    assert updated.lock_version == 1 and updated.updated_by_actor_id == "operator-1"
    with pytest.raises(ValidationError, match="Optimistic lock"):
        update_versioned(
            curriculum,
            expected_lock_version=0,
            actor_id="operator-2",
            changes={"name": "Stale"},
        )
    curriculum.effective_to = date(2025, 1, 1)
    with pytest.raises(ValidationError, match="Periode efektif"):
        curriculum.full_clean()


@pytest.mark.django_db
def test_transaction_rollback_foreign_key_and_deadlock_retry():
    curriculum = CurriculumVersion.objects.create(
        program_code="SI", name="Kurikulum SI", cohort_from=2026
    )
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            Course.objects.create(
                curriculum=curriculum,
                code="SI101",
                name="Pengantar",
                credits=3,
                recommended_semester=1,
                term="odd",
            )
            raise RuntimeError("rollback")
    assert not Course.objects.filter(code="SI101").exists()

    course = Course.objects.create(
        curriculum=curriculum,
        code="SI102",
        name="Basis Data",
        credits=3,
        recommended_semester=2,
        term="even",
    )
    with pytest.raises(ProtectedError):
        curriculum.delete()

    attempts = 0

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            error = OperationalError("deadlock")
            error.pgcode = "40P01"
            raise error
        return course

    assert run_with_deadlock_retry(operation, attempts=2) == course
    assert attempts == 2


@pytest.mark.django_db
def test_evidence_deduplicates_content_and_enforces_private_manifest(settings, tmp_path):
    settings.EVIDENCE_ROOT = tmp_path
    first = store(
        uploaded=uploaded(),
        owner_id="owner",
        academic_object="submission:1",
        classification="internal",
        period="2026-odd",
    )
    second = store(
        uploaded=uploaded(),
        owner_id="owner",
        academic_object="submission:2",
        classification="internal",
        period="2026-odd",
    )
    assert first.manifest.content_path == second.manifest.content_path
    assert verify_integrity(first) and verify_integrity(second)
    target = tmp_path / first.manifest.content_path
    assert target.stat().st_mode & 0o777 == 0o600
    first.manifest.original_filename = "changed.pdf"
    with pytest.raises(ValidationError, match="immutable"):
        first.manifest.save()
    with pytest.raises(ValidationError, match="tidak boleh dihapus"):
        first.manifest.delete()


@pytest.mark.django_db
def test_evidence_antivirus_quota_tamper_and_status_machine(settings, tmp_path, monkeypatch):
    settings.EVIDENCE_ROOT = tmp_path
    settings.EVIDENCE_ANTIVIRUS_REQUIRED = True
    monkeypatch.setattr("obe.evidence.services._clamav_scan", lambda path: "stream: TestSig OK")
    record = store(
        uploaded=uploaded(b"clean evidence"),
        owner_id="owner",
        academic_object="assessment:1",
        classification="confidential",
    )
    assert record.manifest.scan_status == FileManifest.ScanStatus.CLEAN
    transition(record, target_status=EvidenceRecord.Status.SUBMITTED, actor_id="owner")
    verified = transition(record, target_status=EvidenceRecord.Status.VERIFIED, actor_id="gpm")
    assert verified.verified_by_id == "gpm"

    target = tmp_path / verified.manifest.content_path
    target.write_bytes(b"tampered")
    assert not verify_integrity(verified)
    with pytest.raises(ValidationError, match="verified"):
        verified.delete()

    settings.EVIDENCE_OWNER_QUOTA_BYTES = 4
    with pytest.raises(ValidationError, match="Quota"):
        store(
            uploaded=uploaded(b"large"),
            owner_id="new-owner",
            academic_object="assessment:2",
            classification="internal",
        )


@pytest.mark.django_db
def test_evidence_download_is_scoped_expiring_audited_and_checksum_checked(
    client, settings, tmp_path
):
    settings.EVIDENCE_ROOT = tmp_path
    owner = get_user_model().objects.create_user("evidence-owner")
    stranger = get_user_model().objects.create_user("stranger")
    record = store(
        uploaded=uploaded(b"downloadable"),
        owner_id=owner.get_username(),
        academic_object="submission:download",
        classification="internal",
    )
    with pytest.raises(PermissionDenied):
        issue_download_token(record, stranger)

    token = issue_download_token(record, owner)
    with pytest.raises(PermissionDenied, match="kedaluwarsa"):
        resolve_download(token, owner, max_age=-1)
    client.force_login(owner)
    response = client.get(reverse("evidence-download", args=[record.public_id]), {"token": token})
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith("attachment;")
    assert AuditEvent.objects.filter(
        action="evidence.download", object_id=str(record.public_id)
    ).exists()

    (tmp_path / record.manifest.content_path).write_bytes(b"tampered")
    with pytest.raises(PermissionDenied, match="gagal verifikasi"):
        resolve_download(token, owner)


@pytest.mark.django_db
def test_repository_verifier_detects_tamper(settings, tmp_path):
    settings.EVIDENCE_ROOT = tmp_path
    record = store(
        uploaded=uploaded(b"repository check"),
        owner_id="owner",
        academic_object="submission:verify-command",
        classification="internal",
    )
    call_command("verify_evidence_repository", verbosity=0)
    (tmp_path / record.manifest.content_path).write_bytes(b"tampered")
    with pytest.raises(CommandError, match="1 evidence"):
        call_command("verify_evidence_repository", verbosity=0)


def test_selective_and_full_evidence_restore_verify_100_percent(tmp_path):
    snapshot = tmp_path / "snapshot"
    first = snapshot / "aa" / "bb" / ("a" * 64)
    second = snapshot / "cc" / "dd" / ("b" * 64)
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    inventory = create_inventory(snapshot)

    selective = tmp_path / "selective"
    first_sha = inventory["files"][0]["sha256"]
    assert restore_inventory(snapshot, selective, inventory, selected_sha256={first_sha}) == 1
    assert verify_inventory(selective, inventory, selected_sha256={first_sha})

    full = tmp_path / "full"
    assert restore_inventory(snapshot, full, inventory) == 2
    assert verify_inventory(full, inventory)
    shutil.rmtree(full / "aa")
    assert not verify_inventory(full, inventory)
