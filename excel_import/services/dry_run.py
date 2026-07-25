"""DryRunValidator — validates and classifies staged rows without writes.

Requirements: 5.2, 5.3, 5.4, 5.5, 5.6, 5.7.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from excel_import.errors import SchemaVersionMismatchError, get_message
from excel_import.models import ImportBatch, RowClassification, StagedRow


@dataclass
class DryRunReportEntry:
    """One entry in the dry-run report (Requirement 5.5)."""

    row_index: int
    business_key: str
    classification: str
    cell_errors: list[dict] = field(default_factory=list)


@dataclass
class DryRunReport:
    """The complete dry-run report."""

    batch_id: str = ""
    entries: list[DryRunReportEntry] = field(default_factory=list)
    total_rows: int = 0
    new_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0


class DryRunValidator:
    """Validates staged rows and classifies them without any target write."""

    def __init__(self, registry=None, staging=None):
        self.registry = registry
        self.staging = staging

    def dry_run(self, batch: ImportBatch) -> DryRunReport:
        """Run dry-run validation and classification (Requirements 5.2-5.7).

        No owning-module writes occur.
        """
        # Schema version check (Requirement 5.7)
        if self.registry:
            defn = self.registry.get_version(batch.template_type, batch.schema_version)
            if defn is None:
                msg = get_message("schema_mismatch", version=batch.schema_version)
                raise SchemaVersionMismatchError(
                    problem=msg["problem"],
                    corrective_step=msg["corrective_step"],
                    embedded_version=batch.schema_version,
                )
            definition = defn
        else:
            definition = None

        rows = list(batch.rows.all().order_by("row_index"))

        # Intra-batch duplicate detection (Requirement 5.4)
        key_counts = Counter(r.business_key for r in rows)

        report = DryRunReport(batch_id=str(batch.id), total_rows=len(rows))

        for row in rows:
            errors = self._validate_cells(row, definition) if definition else []

            if errors:
                classification = RowClassification.REJECTED
                report.rejected_count += 1
            elif key_counts[row.business_key] > 1:
                classification = RowClassification.DUPLICATE
                report.duplicate_count += 1
            else:
                # Without current data comparison, classify as NEW
                classification = RowClassification.NEW
                report.new_count += 1

            row.classification = classification
            row.cell_errors = errors
            row.save(update_fields=["classification", "cell_errors"])

            report.entries.append(DryRunReportEntry(
                row_index=row.row_index,
                business_key=row.business_key,
                classification=classification,
                cell_errors=errors,
            ))

        return report

    def _validate_cells(self, row: StagedRow, definition) -> list[dict]:
        """Validate each cell against the definition's rules (Requirement 5.2)."""
        errors = []
        rules = definition.validation_rules or []
        raw = row.raw_values or {}

        for rule in rules:
            field_name = rule.get("field", "")
            rule_type = rule.get("rule", "")
            params = rule.get("params", {})
            value = raw.get(field_name, "")

            if rule_type == "not_empty" and not str(value).strip():
                msg = get_message("cell_empty", field=field_name)
                errors.append({
                    "field": field_name,
                    "problem": msg["problem"],
                    "corrective_step": msg["corrective_step"],
                })
            elif rule_type == "is_number":
                try:
                    num = float(value) if value else None
                    if num is not None:
                        min_val = params.get("min")
                        max_val = params.get("max")
                        if min_val is not None and num < min_val:
                            msg = get_message("cell_invalid", field=field_name, reason=f"harus >= {min_val}")
                            errors.append({"field": field_name, "problem": msg["problem"], "corrective_step": msg["corrective_step"]})
                        if max_val is not None and num > max_val:
                            msg = get_message("cell_invalid", field=field_name, reason=f"harus <= {max_val}")
                            errors.append({"field": field_name, "problem": msg["problem"], "corrective_step": msg["corrective_step"]})
                    elif value == "":
                        # Empty number field for non-required fields is ok
                        pass
                except (ValueError, TypeError):
                    msg = get_message("cell_invalid", field=field_name, reason="bukan angka yang valid")
                    errors.append({"field": field_name, "problem": msg["problem"], "corrective_step": msg["corrective_step"]})

        return errors
