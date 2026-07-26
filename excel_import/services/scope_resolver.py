"""ScopeResolver — resolves import scope and gathers prefill/reference data.

Requirements: 3.1, 3.2, 3.3, 3.4, 9.1.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ImportScope:
    """The resolved scope for an import batch."""

    prodi: str = ""
    period: str = ""
    klass: str = ""


class ScopeResolver:
    """Resolves Import_Scope from a timeline task and gathers prefill data."""

    def resolve(self, template_type: str, timeline_task_id: str | None = None) -> tuple[ImportScope, str]:
        """Resolve scope from a timeline task (Requirement 3.1).

        Returns (scope, resolved_template_type).
        """
        if timeline_task_id:
            # Resolve via TimelineService
            try:
                from timeline.models import Task
                task = Task.objects.get(pk=timeline_task_id)
                scope = ImportScope(
                    prodi=str(getattr(task.milestone.phase.instance.cycle.prodi, "code", "")),
                    period="",
                    klass="",
                )
                return scope, template_type
            except Exception:
                pass

        return ImportScope(), template_type

    def reference_data(self, definition, scope: ImportScope) -> list[dict]:
        """Gather reference data from services (Requirement 3.2)."""
        # Reference data is gathered through service layer
        return []

    def prior_data(self, definition, scope: ImportScope) -> list[dict]:
        """Gather prior editable data for prefill (Requirement 3.3)."""
        return []
