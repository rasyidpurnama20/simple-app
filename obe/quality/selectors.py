from typing import Any

from obe.quality.models import ImprovementAction, QualityFinding


def _finding_node(finding: QualityFinding) -> dict[str, Any]:
    return {
        "id": f"cqi-finding:{finding.id}",
        "type": "cqi-finding",
        "object_id": str(finding.id),
        "version": finding.standard.version,
        "status": finding.status,
        "owner": "",
        "effective_period": finding.scope.get("period", {}),
        "source_record": finding.source_id,
        "object_permission": "quality.view",
        "gate": "cqi",
    }


def _action_node(action: ImprovementAction) -> dict[str, Any]:
    return {
        "id": f"cqi-action:{action.public_id}",
        "type": "cqi-action",
        "object_id": str(action.public_id),
        "version": action.version,
        "status": action.status,
        "owner": str(action.owner_id),
        "effective_period": {"due_at": action.due_at.isoformat()},
        "source_record": str(action.public_id),
        "object_permission": "quality.view",
        "gate": "cqi",
    }


def attainment_quality_paths(
    *, scope_type: str, scope_id: str, outcome_code: str
) -> list[list[dict[str, Any]]]:
    candidates = QualityFinding.objects.select_related("standard").filter(
        standard__metric=outcome_code
    )
    findings = [
        row
        for row in candidates
        if row.scope.get("scope_type") == scope_type and row.scope.get("scope_id") == scope_id
    ]
    paths: list[list[dict[str, Any]]] = []
    for finding in findings:
        finding_node = _finding_node(finding)
        actions = ImprovementAction.objects.filter(finding=finding).select_related("owner")
        if actions:
            paths.extend([[finding_node, _action_node(action)] for action in actions])
        else:
            paths.append([finding_node])
    return paths
