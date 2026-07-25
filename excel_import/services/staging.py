"""StagingArea — persists parsed rows as StagedRow records.

Requirement 5.1: Persist before any owning-module write.
"""

from __future__ import annotations

from dataclasses import dataclass

from excel_import.models import ImportBatch, StagedRow


@dataclass
class ParsedRow:
    """A row parsed from the Data sheet."""

    row_index: int
    raw_values: dict
    business_key: str


class StagingArea:
    """Persists parsed Data rows as StagedRow records."""

    def stage(self, batch: ImportBatch, parsed_rows: list[ParsedRow]) -> None:
        """Persist parsed rows as StagedRow records (Requirement 5.1)."""
        for row in parsed_rows:
            StagedRow.objects.create(
                batch=batch,
                row_index=row.row_index,
                raw_values=row.raw_values,
                business_key=row.business_key,
            )

    def rows(self, batch: ImportBatch) -> list[StagedRow]:
        """Return all staged rows for a batch."""
        return list(batch.rows.all().order_by("row_index"))
