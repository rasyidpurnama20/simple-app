from typing import Any

from django.shortcuts import get_object_or_404

from obe.assessment.models import AssessmentItem, AttainmentSnapshot

TRACE_LEVELS = (
    "pl",
    "cpl",
    "cpmk_program",
    "cpmk_rps",
    "sub_cpmk",
    "indicator",
    "item",
    "criterion",
    "instrument",
    "submission",
    "evidence",
    "score",
)

TRACE_GATES = {
    "pl": "curriculum",
    "cpl": "curriculum",
    "cpmk_program": "curriculum",
    "course": "learning",
    "scope": "learning",
    "cpmk_rps": "rps",
    "sub_cpmk": "rps",
    "indicator": "rps",
    "item": "assessment",
    "criterion": "assessment",
    "instrument": "assessment",
    "submission": "execution",
    "evidence": "execution",
    "score": "score",
    "attainment": "attainment",
    "cqi": "cqi",
    "cqi-finding": "cqi",
    "cqi-action": "cqi",
}


def semantic_attainment(*, course: str = "", outcome: str = "") -> list[dict]:
    scope_type = "course" if course else "program"
    snapshots = AttainmentSnapshot.objects.filter(scope_type=scope_type).exclude(
        status=AttainmentSnapshot.Status.SUPERSEDED
    )
    if course:
        snapshots = snapshots.filter(scope_id=course)
    if outcome:
        snapshots = snapshots.filter(outcome_code=outcome)
    rows = []
    for snapshot in snapshots.order_by("outcome_code"):
        actual = float(snapshot.actual) if snapshot.actual is not None else None
        target = float(snapshot.target)
        rows.append(
            {
                "scope_type": snapshot.scope_type,
                "scope_id": snapshot.scope_id,
                "outcome": snapshot.outcome_code,
                "actual": actual,
                "target": target,
                "denominator": snapshot.denominator,
                "coverage": float(snapshot.coverage),
                "status": (
                    "missing" if actual is None else "met" if actual >= target else "below-target"
                ),
                "formula_version": snapshot.formula_version,
                "snapshot_version": snapshot.snapshot_version,
                "blocking_reasons": snapshot.blocking_reasons,
                "missing_data": snapshot.missing_data,
                "source_versions": snapshot.source_versions,
            }
        )
    return rows


def attainment_portfolio_rows(*, scope_type: str, scope_id: str) -> list[dict[str, Any]]:
    snapshots = (
        AttainmentSnapshot.objects.filter(scope_type=scope_type, scope_id=scope_id)
        .exclude(status=AttainmentSnapshot.Status.SUPERSEDED)
        .order_by("outcome_code", "-snapshot_version")
    )
    return [
        {
            "snapshot_id": str(row.id),
            "outcome_code": row.outcome_code,
            "actual": str(row.actual) if row.actual is not None else None,
            "target": str(row.target),
            "gap": str(row.actual - row.target) if row.actual is not None else None,
            "denominator": row.denominator,
            "coverage": str(row.coverage),
            "formula_version": row.formula_version,
            "snapshot_version": row.snapshot_version,
            "status": row.status,
            "blocking_reasons": row.blocking_reasons,
            "missing_data": row.missing_data,
            "source_versions": row.source_versions,
            "source_checksum": row.source_checksum,
        }
        for row in snapshots
    ]


def _node(level: str, value: Any, *, source_versions: dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        object_id = str(value.get("id") or value.get("code") or "missing")
        return {
            "id": f"{level}:{object_id}",
            "type": level,
            "object_id": object_id,
            "version": value.get("version") or source_versions.get(level),
            "status": value.get("status", "linked"),
            "owner": value.get("owner", ""),
            "effective_period": value.get("effective_period", {}),
            "source_record": value.get("source_record", object_id),
            "object_permission": value.get("object_permission", "trace.view"),
            "gate": TRACE_GATES.get(level, "execution"),
        }
    object_id = str(value) if value not in {None, ""} else "missing"
    return {
        "id": f"{level}:{object_id}",
        "type": level,
        "object_id": object_id,
        "version": source_versions.get(level),
        "status": "gap" if object_id == "missing" else "linked",
        "owner": "",
        "effective_period": {},
        "source_record": object_id if object_id != "missing" else None,
        "object_permission": "trace.view",
        "gate": TRACE_GATES.get(level, "execution"),
    }


def attainment_trace_context(snapshot_id) -> dict[str, str]:
    snapshot = get_object_or_404(AttainmentSnapshot, pk=snapshot_id)
    return {
        "scope_type": snapshot.scope_type,
        "scope_id": snapshot.scope_id,
        "outcome_code": snapshot.outcome_code,
    }


def _unresolved_cqi_path() -> list[dict[str, Any]]:
    return [
        {
            "id": "cqi:missing",
            "type": "cqi",
            "object_id": "missing",
            "version": None,
            "status": "gap",
            "owner": "",
            "effective_period": {},
            "source_record": None,
            "object_permission": "quality.view",
            "gate": "cqi",
        }
    ]


def attainment_trace(
    snapshot_id,
    *,
    direction: str = "forward",
    start: str = "",
    downstream_paths: list[list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if direction not in {"forward", "backward"}:
        raise ValueError("direction harus forward atau backward")
    snapshot = get_object_or_404(AttainmentSnapshot, pk=snapshot_id)
    trace_rows = list(snapshot.contributions.order_by("source_id").values())
    if not trace_rows:
        trace_rows = snapshot.trace
    nodes: dict[str, dict[str, Any]] = {}
    edge_keys: set[tuple[str, str, str]] = set()
    edges = []
    for row in trace_rows:
        path = row.get("path", {})
        chain_nodes = [
            _node(level, path.get(level), source_versions=row.get("source_versions", {}))
            for level in TRACE_LEVELS
        ]
        scope_level = "course" if snapshot.scope_type == "course" else "scope"
        scope_node = _node(
            scope_level,
            {
                "id": snapshot.scope_id,
                "version": snapshot.source_versions.get(scope_level),
                "status": "linked",
                "owner": str(snapshot.generated_by_id or ""),
                "source_record": snapshot.scope_id,
            },
            source_versions=snapshot.source_versions,
        )
        row_nodes = [*chain_nodes[:2], scope_node, *chain_nodes[2:]]
        attainment_node = {
            "id": f"attainment:{snapshot.id}",
            "type": "attainment",
            "object_id": str(snapshot.id),
            "version": snapshot.snapshot_version,
            "status": snapshot.status,
            "owner": str(snapshot.generated_by_id or ""),
            "effective_period": {},
            "source_record": snapshot.source_checksum,
            "object_permission": "trace.view",
            "gate": "attainment",
        }
        row_nodes.append(attainment_node)
        for node in row_nodes:
            nodes[node["id"]] = node
        for source, target in zip(row_nodes, row_nodes[1:], strict=False):
            key = (source["id"], target["id"], row.get("source_id", ""))
            if key in edge_keys:
                continue
            edge_keys.add(key)
            edges.append(
                {
                    "source": source["id"],
                    "target": target["id"],
                    "source_record": row.get("source_id", ""),
                    "weight": str(row.get("weight", "")),
                    "status": "blocked" if row.get("blocking_reasons") else "linked",
                    "reason_codes": row.get("blocking_reasons", []),
                    "gate": target["gate"],
                    "blocks": ["attainment"] if row.get("blocking_reasons") else [],
                }
            )
    attainment_id = f"attainment:{snapshot.id}"
    for path in downstream_paths or [_unresolved_cqi_path()]:
        previous = attainment_id
        for supplied_node in path:
            node = {**supplied_node, "gate": supplied_node.get("gate", "cqi")}
            nodes[node["id"]] = node
            key = (previous, node["id"], str(node.get("source_record") or ""))
            if key not in edge_keys:
                edge_keys.add(key)
                edges.append(
                    {
                        "source": previous,
                        "target": node["id"],
                        "source_record": node.get("source_record"),
                        "weight": "",
                        "status": "gap" if node["status"] == "gap" else "linked",
                        "reason_codes": ["CQI_NOT_LINKED"] if node["status"] == "gap" else [],
                        "gate": "cqi",
                        "blocks": [],
                    }
                )
            previous = node["id"]
    if direction == "backward":
        edges = [{**edge, "source": edge["target"], "target": edge["source"]} for edge in edges]
    if start:
        start_ids = {
            node_id for node_id in nodes if node_id == start or node_id.endswith(f":{start}")
        }
        reachable = set(start_ids)
        changed = True
        while changed:
            changed = False
            for edge in edges:
                if edge["source"] in reachable and edge["target"] not in reachable:
                    reachable.add(edge["target"])
                    changed = True
        nodes = {key: value for key, value in nodes.items() if key in reachable}
        edges = [
            edge for edge in edges if edge["source"] in reachable and edge["target"] in reachable
        ]
    gaps = [node["id"] for node in nodes.values() if node["status"] == "gap"]
    return {
        "snapshot_id": str(snapshot.id),
        "direction": direction,
        "nodes": sorted(nodes.values(), key=lambda row: row["id"]),
        "edges": edges,
        "gaps": gaps,
        "warnings": ["TRACE_GAP_VISIBLE"] if gaps else [],
    }


def assessment_item_payload(item: AssessmentItem, *, can_view_answer_key: bool = False) -> dict:
    """Answer keys are never returned to participant-facing selectors."""
    payload = {
        "public_id": str(item.public_id),
        "code": item.code,
        "prompt": item.prompt,
        "item_type": item.item_type,
        "points": str(item.points),
        "indicator_codes": item.indicator_codes,
        "sub_outcome_codes": item.sub_outcome_codes,
    }
    if can_view_answer_key:
        payload["answer_key"] = item.answer_key
    return payload
