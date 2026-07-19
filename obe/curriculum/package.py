from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from obe.curriculum.models import Course, CurriculumEdge, CurriculumVersion, Outcome
from obe.curriculum.services import calculate_checksum, curriculum_payload
from obe.shared.services import ActorContext, record_change


def export_json_package(curriculum: CurriculumVersion) -> bytes:
    payload = curriculum_payload(curriculum)
    payload["package_checksum"] = calculate_checksum(curriculum)
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()


def _csv_value(value: Any) -> Any:
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def _csv_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows([{key: _csv_value(value) for key, value in row.items()} for row in rows])
    return output.getvalue()


def export_csv_bundle(curriculum: CurriculumVersion) -> dict[str, str]:
    payload = curriculum_payload(curriculum)
    return {
        "curriculum.csv": _csv_table([payload["curriculum"]]),
        "outcomes.csv": _csv_table(payload["outcomes"]),
        "courses.csv": _csv_table(payload["courses"]),
        "edges.csv": _csv_table(payload["edges"]),
        "manifest.csv": _csv_table(
            [
                {
                    "schema_version": payload["schema_version"],
                    "package_checksum": calculate_checksum(curriculum),
                }
            ]
        ),
    }


def _parse_date(value: Any) -> date | None:
    if value in {None, "", "None"}:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_json(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, dict | list):
        return value
    return json.loads(str(value))


def _without_checksum(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("package_checksum", None)
    return normalized


@transaction.atomic
def import_json_package(payload: bytes | str | dict[str, Any], *, actor: ActorContext):
    if isinstance(payload, bytes):
        data = json.loads(payload)
    elif isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload
    required = {"schema_version", "curriculum", "outcomes", "courses", "edges"}
    if set(data) - {"package_checksum"} != required:
        raise ValidationError("Struktur curriculum package tidak lengkap atau memiliki field asing")
    if data["schema_version"] != "curriculum-package/1.0":
        raise ValidationError("Versi curriculum package tidak didukung")
    source_checksum = hashlib.sha256(
        json.dumps(
            _without_checksum(data), sort_keys=True, default=str, separators=(",", ":")
        ).encode()
    ).hexdigest()
    supplied = data.get("package_checksum")
    if supplied and supplied != source_checksum:
        raise ValidationError("Checksum curriculum package tidak cocok")
    metadata = data["curriculum"]
    existing = CurriculumVersion.objects.filter(
        program_code=metadata["program_code"], source_checksum=source_checksum
    ).first()
    if existing:
        return existing
    version = (
        CurriculumVersion.objects.filter(program_code=metadata["program_code"]).aggregate(
            maximum=Max("version")
        )["maximum"]
        or 0
    ) + 1
    curriculum = CurriculumVersion.objects.create(
        program_code=metadata["program_code"],
        program_name=metadata.get("program_name", ""),
        degree_level=metadata.get("degree_level", "sarjana"),
        name=metadata["name"],
        version=version,
        curriculum_year=metadata.get("curriculum_year"),
        cohort_from=metadata["cohort_from"],
        cohort_to=metadata.get("cohort_to"),
        effective_from=_parse_date(metadata.get("effective_from")),
        effective_to=_parse_date(metadata.get("effective_to")),
        status=CurriculumVersion.Status.DRAFT,
        source_checksum=source_checksum,
        approval_snapshot={"imported_checksum": source_checksum},
        created_by_actor_id=actor.actor_id,
        updated_by_actor_id=actor.actor_id,
    )
    for item in data["outcomes"]:
        Outcome.objects.create(
            curriculum=curriculum,
            kind=item["kind"],
            code=item["code"],
            name=item["name"],
            description=item["description"],
            category=item.get("category", ""),
            depth=item.get("depth"),
            knowledge_depth=item.get("knowledge_depth"),
            skill_depth=item.get("skill_depth"),
            attitude_depth=item.get("attitude_depth"),
            owner_role=item.get("owner_role", ""),
            weight=Decimal(str(item.get("weight", 0))),
            target=Decimal(str(item.get("target", 75))),
            version=item.get("version", 1),
            status=item.get("status", "active"),
            effective_from=_parse_date(item.get("effective_from")),
            effective_to=_parse_date(item.get("effective_to")),
            created_by_actor_id=actor.actor_id,
            updated_by_actor_id=actor.actor_id,
        )
    for item in data["courses"]:
        Course.objects.create(
            curriculum=curriculum,
            code=item["code"],
            name=item["name"],
            credits=int(item["credits"]),
            required=bool(item["required"]),
            recommended_semester=int(item["recommended_semester"]),
            term=item["term"],
            prerequisites=_parse_json(item.get("prerequisites"), []),
            capacity=int(item.get("capacity", 40)),
            equivalence_codes=_parse_json(item.get("equivalence_codes"), []),
            version=item.get("version", 1),
            status=item.get("status", "active"),
            effective_from=_parse_date(item.get("effective_from")),
            effective_to=_parse_date(item.get("effective_to")),
            created_by_actor_id=actor.actor_id,
            updated_by_actor_id=actor.actor_id,
        )
    for item in data["edges"]:
        CurriculumEdge.objects.create(
            curriculum=curriculum,
            source_type=item["source_type"],
            source_id=item["source_id"],
            target_type=item["target_type"],
            target_id=item["target_id"],
            allocation_weight=Decimal(str(item["allocation_weight"])),
            allocation_method=item.get("allocation_method", "explicit"),
            approval_reference=item.get("approval_reference", ""),
            is_unallocated=bool(item.get("is_unallocated", False)),
            version=item.get("version", 1),
            status=item.get("status", "active"),
            effective_from=_parse_date(item.get("effective_from")),
            effective_to=_parse_date(item.get("effective_to")),
            created_by_actor_id=actor.actor_id,
            updated_by_actor_id=actor.actor_id,
        )
    record_change(
        actor=actor,
        action="import.curriculum-package",
        object_type="curriculum",
        object_id=str(curriculum.public_id),
        summary=f"Curriculum package diimpor sebagai versi {version}",
        after={"source_checksum": source_checksum, "version": version},
        reason="Import curriculum package tervalidasi",
    )
    return curriculum


def import_csv_bundle(bundle: dict[str, str], *, actor: ActorContext) -> CurriculumVersion:
    required = {"curriculum.csv", "outcomes.csv", "courses.csv", "edges.csv", "manifest.csv"}
    if set(bundle) != required:
        raise ValidationError("CSV bundle wajib memuat lima file kanonik")

    def rows(name: str) -> list[dict[str, Any]]:
        return list(csv.DictReader(io.StringIO(bundle[name])))

    manifest = rows("manifest.csv")
    if len(manifest) != 1:
        raise ValidationError("CSV manifest harus tepat satu baris")
    curriculum_rows = rows("curriculum.csv")
    if len(curriculum_rows) != 1:
        raise ValidationError("CSV curriculum harus tepat satu baris")
    metadata = curriculum_rows[0]
    for field in ("version", "curriculum_year", "cohort_from", "cohort_to"):
        metadata[field] = int(metadata[field]) if metadata.get(field) else None
    for field in ("effective_from", "effective_to"):
        metadata[field] = _parse_date(metadata.get(field))
    payload = {
        "schema_version": manifest[0]["schema_version"],
        "package_checksum": manifest[0]["package_checksum"],
        "curriculum": metadata,
        "outcomes": rows("outcomes.csv"),
        "courses": rows("courses.csv"),
        "edges": rows("edges.csv"),
    }
    for item in payload["outcomes"]:
        for field in ("depth", "knowledge_depth", "skill_depth", "attitude_depth", "version"):
            item[field] = int(item[field]) if item.get(field) else None
        for field in ("effective_from", "effective_to"):
            item[field] = _parse_date(item.get(field))
    for item in payload["courses"]:
        item["required"] = item["required"].lower() == "true"
        item["prerequisites"] = _parse_json(item.get("prerequisites"), [])
        item["equivalence_codes"] = _parse_json(item.get("equivalence_codes"), [])
        for field in ("credits", "recommended_semester", "capacity", "version"):
            item[field] = int(item[field])
        for field in ("effective_from", "effective_to"):
            item[field] = _parse_date(item.get(field))
    for item in payload["edges"]:
        item["is_unallocated"] = item["is_unallocated"].lower() == "true"
        item["version"] = int(item["version"])
        for field in ("effective_from", "effective_to"):
            item[field] = _parse_date(item.get(field))
    return import_json_package(payload, actor=actor)
