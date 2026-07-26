"""TemplateRegistry — authoritative, versioned catalog of template definitions.

Registers all 8 types; flags 4 implemented and 4 deferred.
Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7.
"""

from __future__ import annotations

from excel_import.errors import DeferredTemplateError, get_message
from excel_import.models import TemplateDefinition


# All 8 registered types with their implementation status
ALL_TYPES = [
    ("Curriculum", True),
    ("CPL", True),
    ("RPS", True),
    ("Rubric", True),
    ("Roster", False),
    ("Grades", False),
    ("Attainment_Measurement", False),
    ("CQI", False),
]


class TemplateRegistry:
    """Authoritative, versioned catalog of template definitions."""

    def list_types(self) -> list[dict]:
        """List all 8 registered types with implementation status."""
        return [
            {"type": t, "is_implemented": impl}
            for t, impl in ALL_TYPES
        ]

    def is_implemented(self, template_type: str) -> bool:
        """Check if a template type is implemented."""
        for t, impl in ALL_TYPES:
            if t == template_type:
                return impl
        return False

    def implemented_types(self) -> list[str]:
        """Return list of implemented type names."""
        return [t for t, impl in ALL_TYPES if impl]

    def require_implemented(self, template_type: str) -> None:
        """Raise DeferredTemplateError if the type is not implemented."""
        if not self.is_implemented(template_type):
            available = self.implemented_types()
            msg = get_message("deferred_type", type=template_type, available=", ".join(available))
            raise DeferredTemplateError(
                problem=msg["problem"],
                corrective_step=msg["corrective_step"],
                available_types=available,
            )

    def get_current(self, template_type: str) -> TemplateDefinition:
        """Get the latest version of a template definition."""
        self.require_implemented(template_type)
        defn = TemplateDefinition.objects.filter(
            template_type=template_type, is_implemented=True
        ).order_by("-created_at").first()
        if defn is None:
            # Auto-seed if not found
            defn = self._seed_definition(template_type)
        return defn

    def get_version(self, template_type: str, schema_version: str) -> TemplateDefinition | None:
        """Get a specific version of a template definition."""
        return TemplateDefinition.objects.filter(
            template_type=template_type, schema_version=schema_version
        ).first()

    def _seed_definition(self, template_type: str) -> TemplateDefinition:
        """Auto-seed a definition from the definitions directory."""
        from excel_import.definitions.seeds import DEFINITIONS
        defn_data = DEFINITIONS.get(template_type)
        if not defn_data:
            from excel_import.errors import DomainError
            raise DomainError(
                problem=f"Definisi untuk tipe '{template_type}' tidak ditemukan.",
                corrective_step="Hubungi administrator.",
            )
        defn, _ = TemplateDefinition.objects.get_or_create(
            template_type=template_type,
            schema_version=defn_data["schema_version"],
            defaults={
                "is_implemented": True,
                "fields": defn_data["fields"],
                "reference_sources": defn_data["reference_sources"],
                "validation_rules": defn_data["validation_rules"],
                "business_key": defn_data["business_key"],
            },
        )
        return defn

    @staticmethod
    def seed_all_definitions() -> int:
        """Seed all definitions from the definitions directory (append-only)."""
        from excel_import.definitions.seeds import DEFINITIONS, DEFERRED_TYPES
        count = 0
        for ttype, data in DEFINITIONS.items():
            _, created = TemplateDefinition.objects.get_or_create(
                template_type=ttype,
                schema_version=data["schema_version"],
                defaults={
                    "is_implemented": True,
                    "fields": data["fields"],
                    "reference_sources": data["reference_sources"],
                    "validation_rules": data["validation_rules"],
                    "business_key": data["business_key"],
                },
            )
            if created:
                count += 1
        for ttype in DEFERRED_TYPES:
            _, created = TemplateDefinition.objects.get_or_create(
                template_type=ttype,
                schema_version="0.0.0",
                defaults={
                    "is_implemented": False,
                    "fields": [],
                    "reference_sources": [],
                    "validation_rules": [],
                    "business_key": [],
                },
            )
            if created:
                count += 1
        return count
