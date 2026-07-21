from django.core.management import call_command
from django.core.management.base import BaseCommand

from obe.curriculum.models import CurriculumVersion, Outcome
from obe.identity.services import ensure_demo_assignments

DEMO_CURRICULUM_SOURCE_IDS = {
    "CURR-LEGACY-DEMO-V1",
    "CURR-S1IF-2024-V1",
}
DEMO_OUTCOME_COUNTS = {
    Outcome.Kind.PL: 5,
    Outcome.Kind.CPL: 12,
    Outcome.Kind.BK: 18,
    Outcome.Kind.CPMK: 31,
}


def demo_catalog_is_complete() -> bool:
    """Return true only after the atomic v5 import has populated its core catalog."""
    curricula = CurriculumVersion.objects.filter(source_id__in=DEMO_CURRICULUM_SOURCE_IDS)
    if set(curricula.values_list("source_id", flat=True)) != DEMO_CURRICULUM_SOURCE_IDS:
        return False
    current = curricula.filter(source_id="CURR-S1IF-2024-V1").first()
    if current is None or current.courses.count() < 77:
        return False
    return all(
        current.outcomes.filter(kind=kind).count() >= expected
        for kind, expected in DEMO_OUTCOME_COUNTS.items()
    )


class Command(BaseCommand):
    help = "Seed dataset sintetis OBE v5 dan akun demo secara idempotent"

    def handle(self, *args, **options):
        if demo_catalog_is_complete():
            ensure_demo_assignments()
            self.stdout.write(
                self.style.SUCCESS(
                    "Seed OBE v5 sudah tersedia; data kurikulum immutable dipertahankan "
                    "dan akun demo disinkronkan."
                )
            )
            return
        call_command("import_obe_sample", verbosity=options.get("verbosity", 1))
