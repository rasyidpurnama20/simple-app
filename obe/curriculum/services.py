from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from obe.curriculum.models import Course, CurriculumEdge, CurriculumVersion, Outcome
from obe.shared.services import ActorContext, record_change

EXPECTED_COUNTS = {"PL": 5, "CPL": 12, "BK": 18, "CPMK": 31, "COURSE": 77}
NODE_ORDER = {"PL": 0, "CPL": 1, "BK": 2, "COURSE": 3, "CPMK": 4}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()


def curriculum_payload(curriculum: CurriculumVersion) -> dict[str, Any]:
    return {
        "schema_version": "curriculum-package/1.0",
        "curriculum": {
            "program_code": curriculum.program_code,
            "program_name": curriculum.program_name,
            "degree_level": curriculum.degree_level,
            "name": curriculum.name,
            "version": curriculum.version,
            "curriculum_year": curriculum.curriculum_year,
            "cohort_from": curriculum.cohort_from,
            "cohort_to": curriculum.cohort_to,
            "effective_from": curriculum.effective_from,
            "effective_to": curriculum.effective_to,
        },
        "outcomes": list(
            curriculum.outcomes.order_by("kind", "code", "version").values(
                "kind",
                "code",
                "name",
                "description",
                "category",
                "depth",
                "knowledge_depth",
                "skill_depth",
                "attitude_depth",
                "owner_role",
                "weight",
                "target",
                "version",
                "status",
                "effective_from",
                "effective_to",
            )
        ),
        "courses": list(
            curriculum.courses.order_by("code", "version").values(
                "code",
                "name",
                "credits",
                "required",
                "recommended_semester",
                "term",
                "prerequisites",
                "capacity",
                "equivalence_codes",
                "version",
                "status",
                "effective_from",
                "effective_to",
            )
        ),
        "edges": list(
            curriculum.edges.order_by(
                "source_type", "source_id", "target_type", "target_id", "version"
            ).values(
                "source_type",
                "source_id",
                "target_type",
                "target_id",
                "allocation_weight",
                "allocation_method",
                "approval_reference",
                "is_unallocated",
                "version",
                "status",
                "effective_from",
                "effective_to",
            )
        ),
    }


def calculate_checksum(curriculum: CurriculumVersion) -> str:
    return hashlib.sha256(_canonical(curriculum_payload(curriculum))).hexdigest()


def allocation_report(curriculum: CurriculumVersion) -> dict[str, Any]:
    totals: dict[tuple[str, str, str], Decimal] = defaultdict(Decimal)
    unapproved: list[dict[str, str]] = []
    unallocated: list[dict[str, str]] = []
    for edge in curriculum.edges.filter(status="active"):
        key = (edge.source_type, edge.source_id, edge.target_type)
        totals[key] += edge.allocation_weight
        reference = {
            "source_type": edge.source_type,
            "source_id": edge.source_id,
            "target_type": edge.target_type,
            "target_id": edge.target_id,
        }
        if edge.is_unallocated:
            unallocated.append(reference)
        elif not edge.approval_reference:
            unapproved.append(reference)
    invalid = [
        {
            "source_type": key[0],
            "source_id": key[1],
            "target_type": key[2],
            "total": str(total),
        }
        for key, total in totals.items()
        if abs(total - Decimal("100")) > Decimal("0.01")
    ]
    totals_valid = bool(totals) and not invalid
    return {
        "valid": totals_valid and not unapproved and not unallocated,
        "totals_valid": totals_valid,
        "invalid": invalid,
        "unapproved": unapproved,
        "unallocated": unallocated,
        "parents": len(totals),
    }


def catalog_report(curriculum: CurriculumVersion, *, strict_counts: bool = True) -> dict[str, Any]:
    outcomes = curriculum.outcomes.filter(status="active")
    courses = curriculum.courses.filter(status="active")
    counts = {kind: outcomes.filter(kind=kind).count() for kind in ("PL", "CPL", "BK", "CPMK")}
    counts["COURSE"] = courses.count()
    count_errors = {
        kind: {"expected": expected, "actual": counts[kind]}
        for kind, expected in EXPECTED_COUNTS.items()
        if strict_counts and counts[kind] != expected
    }
    weight_errors = []
    for kind in ("PL", "CPL", "BK", "CPMK"):
        total = sum(outcomes.filter(kind=kind).values_list("weight", flat=True), Decimal("0"))
        if strict_counts and abs(total - Decimal("100")) > Decimal("0.01"):
            weight_errors.append({"kind": kind, "total": str(total)})
    incomplete = []
    for outcome in outcomes:
        if not outcome.code or not outcome.description or not outcome.name:
            incomplete.append(f"{outcome.kind}:{outcome.code or outcome.pk}")
        if outcome.kind == Outcome.Kind.BK and (
            not outcome.category or outcome.depth is None or not outcome.owner_role
        ):
            incomplete.append(f"BK:{outcome.code}:metadata")
    course_rows = list(courses)
    course_by_code = {course.code: course for course in course_rows}
    prerequisite_graph: dict[str, set[str]] = defaultdict(set)
    prerequisite_errors = []
    for course in course_rows:
        if not course.code or course.credits <= 0 or not 1 <= course.recommended_semester <= 8:
            incomplete.append(f"COURSE:{course.code or course.pk}")
        for prerequisite in dict.fromkeys(course.prerequisites):
            if prerequisite == course.code:
                prerequisite_errors.append({"course": course.code, "reason": "self"})
            elif prerequisite not in course_by_code:
                prerequisite_errors.append(
                    {"course": course.code, "prerequisite": prerequisite, "reason": "orphan"}
                )
            else:
                prerequisite_graph[course.code].add(prerequisite)
                if course_by_code[prerequisite].recommended_semester >= course.recommended_semester:
                    prerequisite_errors.append(
                        {
                            "course": course.code,
                            "prerequisite": prerequisite,
                            "reason": "semester-order",
                        }
                    )
    if _has_dependency_cycle(prerequisite_graph):
        prerequisite_errors.append({"reason": "cycle"})
    required = sum(courses.filter(required=True).values_list("credits", flat=True))
    elective = sum(courses.filter(required=False).values_list("credits", flat=True))
    credit_valid = required == 126 and elective >= 18 and required + 18 >= 144
    return {
        "valid": (
            not count_errors
            and not weight_errors
            and not incomplete
            and not prerequisite_errors
            and credit_valid
        ),
        "counts": counts,
        "count_errors": count_errors,
        "weight_errors": weight_errors,
        "incomplete": incomplete,
        "prerequisite_errors": prerequisite_errors,
        "required_credits": required,
        "elective_credits": elective,
        "credit_valid": credit_valid,
    }


def _has_dependency_cycle(graph: dict[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(target) for target in graph.get(node, set())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def _node_sets(curriculum: CurriculumVersion) -> dict[str, set[str]]:
    nodes = {
        kind: set(
            curriculum.outcomes.filter(kind=kind, status="active").values_list("code", flat=True)
        )
        for kind in ("PL", "CPL", "BK", "CPMK")
    }
    nodes["COURSE"] = set(curriculum.courses.filter(status="active").values_list("code", flat=True))
    return nodes


def traceability_report(curriculum: CurriculumVersion) -> dict[str, Any]:
    nodes = _node_sets(curriculum)
    edges = list(curriculum.edges.filter(status="active", is_unallocated=False))
    orphan = []
    invalid_direction = []
    duplicates = []
    seen_edges: set[tuple[str, str, str, str]] = set()
    outbound: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    inbound: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for edge in edges:
        edge_key = (edge.source_type, edge.source_id, edge.target_type, edge.target_id)
        if edge_key in seen_edges:
            duplicates.append(edge_key)
        seen_edges.add(edge_key)
        source = (edge.source_type, edge.source_id)
        target = (edge.target_type, edge.target_id)
        if edge.source_id not in nodes.get(
            edge.source_type, set()
        ) or edge.target_id not in nodes.get(edge.target_type, set()):
            orphan.append({"source": source, "target": target})
            continue
        if NODE_ORDER.get(edge.source_type, 999) >= NODE_ORDER.get(edge.target_type, -1):
            invalid_direction.append({"source": source, "target": target})
        outbound[source].add(target)
        inbound[target].add(source)
    gaps = []
    expectations = {
        "PL": (False, {"CPL"}),
        "CPL": (True, {"BK", "CPMK"}),
        "BK": (True, {"COURSE"}),
        "COURSE": (True, {"CPMK"}),
        "CPMK": (True, set()),
    }
    for node_type, identifiers in nodes.items():
        require_inbound, target_types = expectations[node_type]
        for identifier in identifiers:
            node = (node_type, identifier)
            if require_inbound and not inbound[node]:
                gaps.append({"node": node, "missing": "inbound"})
            for target_type in target_types:
                if not any(target[0] == target_type for target in outbound[node]):
                    gaps.append({"node": node, "missing": f"outbound:{target_type}"})
    cycle = _has_cycle(outbound)
    return {
        "valid": not orphan and not invalid_direction and not duplicates and not gaps and not cycle,
        "orphan": orphan,
        "invalid_direction": invalid_direction,
        "duplicates": duplicates,
        "gaps": gaps,
        "cycle": cycle,
        "nodes": sum(len(values) for values in nodes.values()),
        "edges": len(edges),
    }


def _has_cycle(graph: dict[tuple[str, str], set[tuple[str, str]]]) -> bool:
    indegree: dict[tuple[str, str], int] = defaultdict(int)
    nodes = set(graph)
    for targets in graph.values():
        nodes.update(targets)
        for target in targets:
            indegree[target] += 1
    queue = deque(node for node in nodes if indegree[node] == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for target in graph.get(node, set()):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    return visited != len(nodes)


def trace_paths(
    curriculum: CurriculumVersion,
    *,
    node_type: str,
    node_id: str,
    reverse: bool = False,
) -> list[list[tuple[str, str]]]:
    adjacency: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for edge in curriculum.edges.filter(status="active", is_unallocated=False):
        source = (edge.source_type, edge.source_id)
        target = (edge.target_type, edge.target_id)
        adjacency[target if reverse else source].add(source if reverse else target)
    start = (node_type, node_id)
    paths: list[list[tuple[str, str]]] = []
    stack = [(start, [start])]
    while stack:
        node, path = stack.pop()
        targets = adjacency.get(node, set())
        if not targets:
            paths.append(path)
            continue
        for target in sorted(targets, reverse=True):
            if target not in path:
                stack.append((target, [*path, target]))
    return sorted(paths)


def impacted_nodes(
    curriculum: CurriculumVersion,
    *,
    node_type: str,
    node_id: str,
    reverse: bool = False,
) -> list[tuple[str, str]]:
    start = (node_type, node_id)
    return sorted(
        {
            node
            for path in trace_paths(
                curriculum,
                node_type=node_type,
                node_id=node_id,
                reverse=reverse,
            )
            for node in path
            if node != start
        }
    )


@transaction.atomic
def approve_allocations(
    curriculum: CurriculumVersion,
    *,
    actor: ActorContext,
    approval_reference: str,
) -> int:
    if curriculum.status == CurriculumVersion.Status.ACTIVE:
        raise ValidationError("Mapping aktif tidak dapat disetujui ulang")
    if not approval_reference.strip():
        raise ValidationError("Approval allocation memerlukan referensi")
    edges = list(
        CurriculumEdge.objects.select_for_update().filter(
            curriculum=curriculum,
            status="active",
            is_unallocated=False,
        )
    )
    for edge in edges:
        edge.approval_reference = approval_reference
        edge.updated_by_actor_id = actor.actor_id
        edge.save(update_fields=["approval_reference", "updated_by_actor_id", "updated_at"])
    record_change(
        actor=actor,
        action="approval.curriculum-allocation",
        object_type="curriculum",
        object_id=str(curriculum.public_id),
        summary=f"{len(edges)} allocation disetujui",
        after={"approval_reference": approval_reference, "edges": len(edges)},
        reason=approval_reference,
    )
    return len(edges)


@transaction.atomic
def submit_for_review(curriculum: CurriculumVersion, *, actor: ActorContext) -> CurriculumVersion:
    locked = CurriculumVersion.objects.select_for_update().get(pk=curriculum.pk)
    if locked.status != CurriculumVersion.Status.DRAFT:
        raise ValidationError("Hanya kurikulum draft yang dapat diajukan")
    locked.status = CurriculumVersion.Status.REVIEW
    locked.reviewed_by_actor_id = actor.actor_id
    locked.reviewed_at = timezone.now()
    locked.save()
    record_change(
        actor=actor,
        action="curriculum.review-submitted",
        object_type="curriculum",
        object_id=str(locked.public_id),
        summary="Kurikulum diajukan untuk review",
        after={"status": locked.status},
    )
    return locked


@transaction.atomic
def approve_curriculum(
    curriculum: CurriculumVersion,
    *,
    actor: ActorContext,
    documents: list[dict[str, Any]],
    strict_catalog: bool = True,
) -> CurriculumVersion:
    locked = CurriculumVersion.objects.select_for_update().get(pk=curriculum.pk)
    if locked.status != CurriculumVersion.Status.REVIEW:
        raise ValidationError("Kurikulum harus berstatus review")
    if actor.actor_id in {locked.created_by_actor_id, locked.reviewed_by_actor_id}:
        raise ValidationError("Maker/reviewer tidak boleh menjadi approver")
    if not documents:
        raise ValidationError("Approval memerlukan dokumen pengesahan internal")
    catalog = catalog_report(locked, strict_counts=strict_catalog)
    allocations = allocation_report(locked)
    traceability = traceability_report(locked)
    if not catalog["valid"] or not allocations["valid"] or not traceability["valid"]:
        raise ValidationError(
            {"catalog": catalog, "allocations": allocations, "traceability": traceability}
        )
    locked.approved_by_actor_id = actor.actor_id
    locked.approved_at = timezone.now()
    locked.approval_documents = documents
    locked.approval_snapshot = {
        **locked.approval_snapshot,
        "approved": True,
        "catalog": catalog,
        "allocations": allocations,
        "traceability": traceability,
    }
    locked.save()
    record_change(
        actor=actor,
        action="approval.curriculum",
        object_type="curriculum",
        object_id=str(locked.public_id),
        summary="Paket kurikulum disetujui",
        after={"version": locked.version, "approved": True},
        reason="Dokumen pengesahan dan seluruh gate paket terverifikasi",
    )
    return locked


def _periods_overlap(first: CurriculumVersion, second: CurriculumVersion) -> bool:
    cohort_overlap = (first.cohort_to is None or first.cohort_to >= second.cohort_from) and (
        second.cohort_to is None or second.cohort_to >= first.cohort_from
    )
    first_start = first.effective_from or date.min
    first_end = first.effective_to or date.max
    second_start = second.effective_from or date.min
    second_end = second.effective_to or date.max
    return cohort_overlap and first_start <= second_end and second_start <= first_end


@transaction.atomic
def activate(
    curriculum: CurriculumVersion,
    *,
    actor: ActorContext | None = None,
    integrity_verified: bool = False,
    strict_catalog: bool = True,
) -> CurriculumVersion:
    actor = actor or ActorContext("system", "system", "curriculum")
    locked = CurriculumVersion.objects.select_for_update().get(pk=curriculum.pk)
    if locked.status != CurriculumVersion.Status.REVIEW or not locked.approval_snapshot.get(
        "approved"
    ):
        raise ValidationError("Kurikulum harus direview dan disetujui sebelum aktivasi")
    if actor.actor_id in {
        locked.created_by_actor_id,
        locked.reviewed_by_actor_id,
        locked.approved_by_actor_id,
    }:
        raise ValidationError("Maker/reviewer/approver tidak boleh menjadi activator")
    if not integrity_verified:
        raise ValidationError("Integrity validation harus verified sebelum aktivasi")
    catalog = catalog_report(locked, strict_counts=strict_catalog)
    allocations = allocation_report(locked)
    traceability = traceability_report(locked)
    if not catalog["valid"] or not allocations["valid"] or not traceability["valid"]:
        raise ValidationError(
            {"catalog": catalog, "allocations": allocations, "traceability": traceability}
        )
    checksum = calculate_checksum(locked)
    active_versions = list(
        CurriculumVersion.objects.select_for_update().filter(
            program_code=locked.program_code,
            status=CurriculumVersion.Status.ACTIVE,
        )
    )
    for previous in active_versions:
        if _periods_overlap(previous, locked):
            previous.status = CurriculumVersion.Status.ARCHIVED
            previous.archive_reason = f"Superseded by version {locked.version}"
            previous.save(update_fields=["status", "archive_reason", "updated_at"])
    locked.checksum = checksum
    locked.status = CurriculumVersion.Status.ACTIVE
    locked.activated_at = timezone.now()
    locked.save()
    record_change(
        actor=actor,
        action="approval.curriculum-activated",
        object_type="curriculum",
        object_id=str(locked.public_id),
        summary="Kurikulum diaktifkan",
        after={"version": locked.version, "checksum": checksum},
        reason="Seluruh gate katalog, allocation, traceability, dan integritas lulus",
        event_type="curriculum.activated",
        aggregate_version=locked.version,
    )
    return locked


@transaction.atomic
def rollback_activation(
    current: CurriculumVersion,
    target: CurriculumVersion,
    *,
    actor: ActorContext,
) -> CurriculumVersion:
    versions = {
        item.pk: item
        for item in CurriculumVersion.objects.select_for_update()
        .filter(pk__in=[current.pk, target.pk])
        .order_by("pk")
    }
    locked_current = versions.get(current.pk)
    locked_target = versions.get(target.pk)
    if not locked_current or not locked_target:
        raise ValidationError("Versi rollback tidak ditemukan")
    if locked_current.program_code != locked_target.program_code:
        raise ValidationError("Rollback lintas program tidak diizinkan")
    if locked_current.status != CurriculumVersion.Status.ACTIVE:
        raise ValidationError("Versi saat ini harus aktif")
    if locked_target.status != CurriculumVersion.Status.ARCHIVED:
        raise ValidationError("Target rollback harus berupa versi arsip")
    if not locked_target.approval_snapshot.get("approved") or not locked_target.checksum:
        raise ValidationError("Target rollback tidak memiliki approval/checksum yang sah")
    if calculate_checksum(locked_target) != locked_target.checksum:
        raise ValidationError("Checksum target rollback tidak cocok")
    locked_current.status = CurriculumVersion.Status.ARCHIVED
    locked_current.archive_reason = f"Rollback to version {locked_target.version}"
    locked_current.save(update_fields=["status", "archive_reason", "updated_at"])
    locked_target.status = CurriculumVersion.Status.ACTIVE
    locked_target.archive_reason = ""
    locked_target.save(update_fields=["status", "archive_reason", "updated_at"])
    record_change(
        actor=actor,
        action="approval.curriculum-rollback",
        object_type="curriculum",
        object_id=str(locked_target.public_id),
        summary=f"Aktivasi dikembalikan ke versi {locked_target.version}",
        before={"active_version": locked_current.version},
        after={"active_version": locked_target.version},
        reason="Rollback terkontrol ke paket yang telah disetujui dan checksum-valid",
        event_type="curriculum.rolled-back",
        aggregate_version=locked_target.version,
    )
    return locked_target


@transaction.atomic
def clone_curriculum(
    source: CurriculumVersion,
    *,
    actor: ActorContext,
    effective_from: date | None = None,
) -> CurriculumVersion:
    source = CurriculumVersion.objects.select_for_update().get(pk=source.pk)
    version = (
        CurriculumVersion.objects.filter(program_code=source.program_code).aggregate(
            maximum=Max("version")
        )["maximum"]
        or 0
    ) + 1
    clone = CurriculumVersion.objects.create(
        program_code=source.program_code,
        program_name=source.program_name,
        degree_level=source.degree_level,
        name=f"{source.name} v{version}",
        version=version,
        curriculum_year=source.curriculum_year,
        cohort_from=source.cohort_from,
        cohort_to=source.cohort_to,
        effective_from=effective_from or source.effective_from,
        effective_to=source.effective_to,
        status=CurriculumVersion.Status.DRAFT,
        source_checksum=source.checksum or calculate_checksum(source),
        approval_snapshot={"cloned_from": str(source.public_id), "source_version": source.version},
        created_by_actor_id=actor.actor_id,
        updated_by_actor_id=actor.actor_id,
    )
    Outcome.objects.bulk_create(
        [
            Outcome(
                curriculum=clone,
                kind=item.kind,
                code=item.code,
                name=item.name,
                description=item.description,
                category=item.category,
                depth=item.depth,
                knowledge_depth=item.knowledge_depth,
                skill_depth=item.skill_depth,
                attitude_depth=item.attitude_depth,
                owner_role=item.owner_role,
                weight=item.weight,
                target=item.target,
                version=item.version + 1,
                status=item.status,
                effective_from=effective_from or item.effective_from,
                effective_to=item.effective_to,
                created_by_actor_id=actor.actor_id,
                updated_by_actor_id=actor.actor_id,
            )
            for item in source.outcomes.all()
        ]
    )
    Course.objects.bulk_create(
        [
            Course(
                curriculum=clone,
                code=item.code,
                name=item.name,
                credits=item.credits,
                required=item.required,
                recommended_semester=item.recommended_semester,
                term=item.term,
                prerequisites=item.prerequisites,
                capacity=item.capacity,
                equivalence_codes=item.equivalence_codes,
                version=item.version + 1,
                status=item.status,
                effective_from=effective_from or item.effective_from,
                effective_to=item.effective_to,
                created_by_actor_id=actor.actor_id,
                updated_by_actor_id=actor.actor_id,
            )
            for item in source.courses.all()
        ]
    )
    CurriculumEdge.objects.bulk_create(
        [
            CurriculumEdge(
                curriculum=clone,
                source_type=item.source_type,
                source_id=item.source_id,
                target_type=item.target_type,
                target_id=item.target_id,
                allocation_weight=item.allocation_weight,
                allocation_method=item.allocation_method,
                approval_reference="",
                is_unallocated=item.is_unallocated,
                version=item.version + 1,
                status=item.status,
                effective_from=effective_from or item.effective_from,
                effective_to=item.effective_to,
                created_by_actor_id=actor.actor_id,
                updated_by_actor_id=actor.actor_id,
            )
            for item in source.edges.all()
        ]
    )
    record_change(
        actor=actor,
        action="curriculum.cloned",
        object_type="curriculum",
        object_id=str(clone.public_id),
        summary=f"Kurikulum versi {source.version} diklon ke versi {clone.version}",
        after={"source": str(source.public_id), "version": clone.version},
    )
    return clone


def curriculum_diff(
    first: CurriculumVersion, second: CurriculumVersion
) -> dict[str, list[dict[str, Any]]]:
    def indexed(payload):
        result = {}
        for item in payload["outcomes"]:
            result[f"outcome:{item['kind']}:{item['code']}"] = item
        for item in payload["courses"]:
            result[f"course:{item['code']}"] = item
        for item in payload["edges"]:
            result[
                "edge:"
                + ":".join(
                    str(item[key])
                    for key in ("source_type", "source_id", "target_type", "target_id")
                )
            ] = item
        return result

    left, right = indexed(curriculum_payload(first)), indexed(curriculum_payload(second))
    added = [{"key": key, "after": right[key]} for key in sorted(right.keys() - left.keys())]
    removed = [{"key": key, "before": left[key]} for key in sorted(left.keys() - right.keys())]
    changed = [
        {"key": key, "before": left[key], "after": right[key]}
        for key in sorted(left.keys() & right.keys())
        if left[key] != right[key]
    ]
    return {"added": added, "removed": removed, "changed": changed}


def course_progress(
    curriculum: CurriculumVersion, records: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    rows = []
    earned_required = earned_elective = 0
    required_total = sum(
        curriculum.courses.filter(required=True, status="active").values_list("credits", flat=True)
    )
    elective_target = 18
    for course in curriculum.courses.filter(status="active").order_by(
        "recommended_semester", "code"
    ):
        record = records.get(course.code, {})
        if record.get("equivalent"):
            status = "equivalent"
        elif record.get("passed"):
            status = "passed"
        elif record.get("attempts", 0) > 1:
            status = "repeat"
        elif record.get("in_progress"):
            status = "in_progress"
        else:
            status = "not_taken"
        if status in {"passed", "equivalent"}:
            if course.required:
                earned_required += course.credits
            else:
                earned_elective += course.credits
        rows.append(
            {
                "code": course.code,
                "name": course.name,
                "credits": course.credits,
                "required": course.required,
                "status": status,
            }
        )
    earned_for_target = min(earned_required, required_total) + min(earned_elective, elective_target)
    return {
        "courses": rows,
        "earned_required": earned_required,
        "earned_elective": earned_elective,
        "remaining_required": max(0, required_total - earned_required),
        "remaining_elective": max(0, elective_target - earned_elective),
        "progress_percent": (
            Decimal(earned_for_target) / Decimal(required_total + elective_target) * 100
        ).quantize(Decimal("0.01"))
        if required_total + elective_target
        else Decimal("0"),
    }
