"""RPS_Module service layer.

All RPS business logic: create_rps, add_cpmk, define_rubric, submit_rps.
Cross-module access to CurriculumService for CPL derivation validation.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from core.exceptions import DomainError
from core.models import DemoUser

from .models import (
    AssessmentInstrument,
    CPMK,
    RPS,
    RPSStatus,
    Rubric,
    RubricCriterion,
    RubricLevel,
    Score,
    SubCPMK,
    SubCPMKIndicator,
)


class RPSService:
    """Business logic for the RPS_Module."""

    # -- RPS creation (Requirement 8.1) -----------------------------------

    @staticmethod
    @transaction.atomic
    def create_rps(course_id, curriculum_id, class_name: str, period: str, actor) -> RPS:
        """Create an RPS bound to one course/curriculum/class/period."""
        from curriculum.models import Course, Curriculum

        actor_obj = _resolve_actor(actor)
        course = Course.objects.get(pk=course_id)
        curriculum = Curriculum.objects.get(pk=curriculum_id)

        rps = RPS.objects.create(
            course=course,
            curriculum=curriculum,
            class_name=class_name,
            period=period,
            prodi=curriculum.prodi,
            owner=actor_obj,
            creator=actor_obj,
            status=RPSStatus.DRAFT,
        )
        return rps

    # -- CPMK derivation (Requirements 8.2, 8.5) -------------------------

    @staticmethod
    @transaction.atomic
    def add_cpmk(rps_id, cpl_ids: list, data: dict, actor) -> CPMK:
        """Add a CPMK to an RPS, deriving only from bound-curriculum CPLs.

        Rejects CPLs that don't belong to the RPS's bound curriculum with an
        explainable message (Requirements 8.2, 8.5).
        """
        from curriculum.models import CPL

        rps = RPS.objects.get(pk=rps_id)

        # Validate all CPLs belong to the bound curriculum
        valid_cpls = CPL.objects.filter(
            pk__in=cpl_ids, curriculum=rps.curriculum
        )
        valid_ids = set(valid_cpls.values_list("pk", flat=True))
        foreign_ids = set(cpl_ids) - valid_ids

        if foreign_ids:
            raise DomainError(
                "Beberapa CPL yang dipilih tidak termasuk dalam kurikulum yang terikat pada RPS ini.",
                "Gunakan hanya CPL dari kurikulum yang terkait dengan RPS ini. "
                "CPL yang tidak valid telah ditolak.",
            )

        cpmk = CPMK.objects.create(
            rps=rps,
            code=data.get("code", ""),
            description=data.get("description", ""),
        )
        cpmk.derived_from.set(valid_cpls)
        return cpmk

    # -- Sub-CPMK management ---------------------------------------------

    @staticmethod
    @transaction.atomic
    def add_sub_cpmk(cpmk_id, data: dict, actor) -> SubCPMK:
        """Add a Sub-CPMK to a CPMK."""
        cpmk = CPMK.objects.get(pk=cpmk_id)
        sub_cpmk = SubCPMK.objects.create(
            cpmk=cpmk,
            code=data.get("code", ""),
            description=data.get("description", ""),
        )
        return sub_cpmk

    @staticmethod
    @transaction.atomic
    def add_sub_cpmk_indicator(sub_cpmk_id, data: dict, actor) -> SubCPMKIndicator:
        """Add an indicator to a Sub-CPMK."""
        sub_cpmk = SubCPMK.objects.get(pk=sub_cpmk_id)
        indicator = SubCPMKIndicator.objects.create(
            sub_cpmk=sub_cpmk,
            code=data.get("code", ""),
            description=data.get("description", ""),
        )
        return indicator

    # -- Assessment instrument and rubric (Requirements 9.1-9.3) ---------

    @staticmethod
    @transaction.atomic
    def add_instrument(rps_id, data: dict, actor) -> AssessmentInstrument:
        """Add an assessment instrument to an RPS."""
        actor_obj = _resolve_actor(actor)
        rps = RPS.objects.get(pk=rps_id)
        instrument = AssessmentInstrument.objects.create(
            rps=rps,
            name=data.get("name", ""),
            description=data.get("description", ""),
            prodi=rps.prodi,
            owner=actor_obj,
            creator=actor_obj,
            status=RPSStatus.DRAFT,
        )
        return instrument

    @staticmethod
    @transaction.atomic
    def define_rubric(instrument_id, criteria: list[dict], actor) -> Rubric:
        """Define a rubric for an instrument with criteria, levels, and mappings.

        Each criterion dict: {name, weight, levels: [{label, score}], indicator_ids: []}
        Requirements 9.1, 9.2, 9.3.
        """
        actor_obj = _resolve_actor(actor)
        instrument = AssessmentInstrument.objects.get(pk=instrument_id)

        # Create or replace rubric
        rubric, created = Rubric.objects.update_or_create(
            instrument=instrument,
            defaults={
                "name": f"Rubric for {instrument.name}",
                "prodi": instrument.prodi,
                "owner": actor_obj,
                "creator": actor_obj,
                "status": RPSStatus.DRAFT,
            },
        )
        if not created:
            # Clear old criteria on redefine
            rubric.criteria.all().delete()

        for idx, crit_data in enumerate(criteria):
            criterion = RubricCriterion.objects.create(
                rubric=rubric,
                name=crit_data.get("name", f"Criterion {idx + 1}"),
                weight=Decimal(str(crit_data.get("weight", 0))),
                order=idx,
            )
            # Create levels
            for lvl_idx, lvl in enumerate(crit_data.get("levels", [])):
                RubricLevel.objects.create(
                    criterion=criterion,
                    label=lvl.get("label", ""),
                    score=Decimal(str(lvl.get("score", 0))),
                    order=lvl_idx,
                )
            # Map indicators
            indicator_ids = crit_data.get("indicator_ids", [])
            if indicator_ids:
                indicators = SubCPMKIndicator.objects.filter(pk__in=indicator_ids)
                criterion.mapped_indicators.set(indicators)

        return rubric

    # -- RPS submission (Requirements 10.1-10.4) --------------------------

    @staticmethod
    @transaction.atomic
    def submit_rps(rps_id, actor) -> RPS:
        """Submit an RPS for review.

        Validates:
        1. Every rubric's criterion weights sum to 100% (Req 10.1, 10.3).
        2. Every Sub_CPMK indicator maps to at least one criterion (Req 10.2, 10.4).
        """
        rps = RPS.objects.get(pk=rps_id)

        # Weight-sum validation (Req 10.1, 10.3)
        instruments = rps.instruments.all().prefetch_related("rubric__criteria")
        for instrument in instruments:
            rubric = getattr(instrument, "rubric", None)
            if rubric is None:
                continue
            criteria = list(rubric.criteria.all())
            if not criteria:
                continue
            total_weight = sum(c.weight for c in criteria)
            if total_weight != Decimal("100"):
                raise DomainError(
                    f"Jumlah bobot kriteria pada rubrik \"{rubric.name}\" "
                    f"adalah {total_weight}%, bukan 100%.",
                    f"Sesuaikan bobot kriteria agar totalnya tepat 100%. "
                    f"Saat ini total adalah {total_weight}%.",
                )

        # Coverage validation (Req 10.2, 10.4)
        all_indicators = SubCPMKIndicator.objects.filter(
            sub_cpmk__cpmk__rps=rps
        )
        mapped_indicator_ids = set(
            RubricCriterion.objects.filter(
                rubric__instrument__rps=rps
            ).values_list("mapped_indicators__pk", flat=True)
        )
        unmapped = [ind for ind in all_indicators if ind.pk not in mapped_indicator_ids]

        if unmapped:
            unmapped_codes = [ind.code for ind in unmapped[:5]]
            more = f" (dan {len(unmapped) - 5} lainnya)" if len(unmapped) > 5 else ""
            raise DomainError(
                f"Terdapat indikator Sub-CPMK yang belum dipetakan ke kriteria rubrik: "
                f"{', '.join(unmapped_codes)}{more}.",
                "Petakan setiap indikator Sub-CPMK ke minimal satu kriteria rubrik.",
            )

        rps.status = RPSStatus.SUBMITTED
        rps.save(update_fields=["status", "modified_time"])
        return rps

    # -- Score management -------------------------------------------------

    @staticmethod
    @transaction.atomic
    def record_score(criterion_id, student_proxy: str, value, actor) -> Score:
        """Record a score for a rubric criterion."""
        criterion = RubricCriterion.objects.get(pk=criterion_id)
        score = Score.objects.create(
            criterion=criterion,
            student_proxy=student_proxy,
            value=Decimal(str(value)),
        )
        return score

    # -- Read helpers for cross-module use --------------------------------

    @staticmethod
    def get_rps(rps_id) -> RPS:
        """Get an RPS by ID."""
        return RPS.objects.get(pk=rps_id)

    @staticmethod
    def get_scores_for_rps(rps_id) -> list[Score]:
        """Get all scores for an RPS."""
        return list(
            Score.objects.filter(
                criterion__rubric__instrument__rps_id=rps_id
            ).select_related("criterion__rubric__instrument")
        )

    @staticmethod
    def get_criteria_for_rps(rps_id) -> list[RubricCriterion]:
        """Get all rubric criteria for an RPS."""
        return list(
            RubricCriterion.objects.filter(
                rubric__instrument__rps_id=rps_id
            ).prefetch_related("mapped_indicators", "levels")
        )

    @staticmethod
    def list_editable(scope, template_type=None):
        """Return editable records for Excel import prefill."""
        return []


def _resolve_actor(actor) -> DemoUser | None:
    """Accept a DemoUser instance or an id and return the DemoUser (or None)."""
    if actor is None:
        return None
    if isinstance(actor, DemoUser):
        return actor
    return DemoUser.objects.filter(pk=actor).first()
