import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError

from obe.curriculum.models import CurriculumEdge, CurriculumVersion


def allocation_report(curriculum: CurriculumVersion) -> dict:
    totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for edge in curriculum.edges.filter(status="active"):
        totals[(edge.source_type, edge.source_id)] += edge.allocation_weight
    invalid = [
        {"source_type": key[0], "source_id": key[1], "total": str(total)}
        for key, total in totals.items()
        if abs(total - Decimal("100")) > Decimal("0.01")
    ]
    return {"valid": not invalid, "invalid": invalid, "parents": len(totals)}


def activate(curriculum: CurriculumVersion) -> CurriculumVersion:
    report = allocation_report(curriculum)
    required = sum(c.credits for c in curriculum.courses.filter(required=True, status="active"))
    elective = sum(c.credits for c in curriculum.courses.filter(required=False, status="active"))
    if not report["valid"]:
        raise ValidationError({"allocation": report["invalid"]})
    if required != 126 or elective < 18:
        raise ValidationError({"credits": f"wajib={required}, pilihan tersedia={elective}"})
    payload = {
        "program": curriculum.program_code,
        "version": curriculum.version,
        "courses": list(curriculum.courses.order_by("code").values("code", "credits", "required")),
        "edges": list(
            CurriculumEdge.objects.filter(curriculum=curriculum)
            .order_by("source_type", "source_id", "target_type", "target_id")
            .values("source_type", "source_id", "target_type", "target_id", "allocation_weight")
        ),
    }
    curriculum.checksum = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()
    curriculum.status = CurriculumVersion.Status.ACTIVE
    curriculum.save(update_fields=["checksum", "status", "updated_at"])
    return curriculum
