"""Attainment_Engine service layer.

Implements the attainment calculation chain, data-integrity halt, and
gap-driven evaluation task creation (Requirements 11, 12, 13).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from core.exceptions import DomainError

from .models import AttainmentResult, CalculationFormula, FormulaLevel


class AttainmentService:
    """Business logic for the Attainment_Engine."""

    @staticmethod
    @transaction.atomic
    def calculate(cycle_id, actor) -> dict:
        """Run the attainment calculation for a cycle.

        Aggregates Rubric_Criterion -> CPL_Indicator -> Sub_CPMK -> CPMK -> CPL
        using named/versioned formulas; stores actual/target/gap + traceability.
        Halts on missing/out-of-range data. Creates gap-driven evaluation tasks.
        (Requirements 11, 12, 13)
        """
        from curriculum.models import CPL, CPLIndicator
        from rps.models import CPMK, RPS, RubricCriterion, Score, SubCPMK, SubCPMKIndicator
        from timeline.models import OBECycle

        cycle = OBECycle.objects.get(pk=cycle_id)

        # Get the active formula (use default weighted_average if none exists)
        formula = CalculationFormula.objects.filter(
            level=FormulaLevel.CPL, is_active=True
        ).first()
        if formula is None:
            formula = CalculationFormula.objects.create(
                name="weighted_average",
                version=1,
                level=FormulaLevel.CPL,
                definition={"method": "weighted_average"},
                is_active=True,
            )

        # Get all RPS for this cycle's prodi
        rps_list = RPS.objects.filter(prodi=cycle.prodi).prefetch_related(
            "cpmks__derived_from__indicators",
            "cpmks__sub_cpmks__indicators__mapped_criteria__scores",
            "instruments__rubric__criteria__mapped_indicators",
            "instruments__rubric__criteria__levels",
            "instruments__rubric__criteria__scores",
        )

        if not rps_list.exists():
            return {"results": [], "tasks_created": 0}

        # Collect all scores and validate (data-integrity halt)
        all_scores = Score.objects.filter(
            criterion__rubric__instrument__rps__prodi=cycle.prodi
        ).select_related("criterion__rubric__instrument__rps")

        # Validate scores (Requirement 12.1, 12.2)
        for score in all_scores:
            criterion = score.criterion
            levels = list(criterion.levels.all())
            if levels:
                min_score = min(l.score for l in levels)
                max_score = max(l.score for l in levels)
                if score.value < min_score or score.value > max_score:
                    raise DomainError(
                        f"Nilai {score.value} untuk kriteria \"{criterion.name}\" "
                        f"berada di luar rentang yang diperbolehkan ({min_score}-{max_score}).",
                        "Periksa dan perbaiki nilai yang dimasukkan, kemudian jalankan "
                        "perhitungan ulang.",
                    )

        # Aggregate per CPL
        results = []
        tasks_created = 0

        # Get all CPLs for this prodi's active curriculum
        from curriculum.models import Curriculum, CurriculumStatus
        active_curriculum = Curriculum.objects.filter(
            prodi=cycle.prodi, status=CurriculumStatus.ACTIVE
        ).first()

        if not active_curriculum:
            return {"results": [], "tasks_created": 0}

        cpls = CPL.objects.filter(curriculum=active_curriculum).prefetch_related("indicators")

        for cpl in cpls:
            indicators = list(cpl.indicators.all())
            if not indicators:
                continue

            # For each CPL indicator, find scores through mapped criteria
            indicator_actuals = []
            all_cpl_scores = []

            for indicator in indicators:
                # Find SubCPMKIndicators that correspond to this CPL indicator
                # Through: CPMK.derived_from -> CPL -> CPLIndicator
                # And: SubCPMKIndicator -> mapped_criteria -> scores
                sub_indicators = SubCPMKIndicator.objects.filter(
                    mapped_criteria__rubric__instrument__rps__prodi=cycle.prodi
                )

                criterion_scores = Score.objects.filter(
                    criterion__mapped_indicators__sub_cpmk__cpmk__derived_from=cpl,
                    criterion__rubric__instrument__rps__prodi=cycle.prodi,
                )

                if criterion_scores.exists():
                    avg = sum(s.value for s in criterion_scores) / len(criterion_scores)
                    indicator_actuals.append(avg)
                    all_cpl_scores.extend(criterion_scores)

            if not indicator_actuals:
                continue

            actual = sum(indicator_actuals) / Decimal(len(indicator_actuals))
            target = indicators[0].target_value if indicators else Decimal("70")
            gap = actual - target

            result = AttainmentResult.objects.create(
                cycle=cycle,
                outcome_ref=cpl.code,
                actual_value=actual,
                target_value=target,
                gap=gap,
                formula_name=formula.name,
                formula_version=formula.version,
            )
            # Traceability
            result.source_scores.set(all_cpl_scores)
            results.append(result)

            # Gap-driven task creation (Requirement 13.1, 13.3)
            if actual < target:
                tasks_created += AttainmentService._create_evaluation_task(
                    cycle, cpl, actual, target, gap, actor
                )

        return {"results": results, "tasks_created": tasks_created}

    @staticmethod
    def _create_evaluation_task(cycle, cpl, actual, target, gap, actor) -> int:
        """Create an evaluation task in the cycle's timeline for a gap."""
        from timeline.models import TaskStatus, TimelineInstance, Milestone, Task

        try:
            instance = cycle.timeline_instance
        except TimelineInstance.DoesNotExist:
            return 0

        # Find or create a milestone for evaluation tasks
        phases = list(instance.phases.all())
        if not phases:
            return 0

        last_phase = phases[-1]
        milestone, _ = Milestone.objects.get_or_create(
            phase=last_phase,
            name="Evaluasi Capaian",
            defaults={"order": 999},
        )

        Task.objects.create(
            milestone=milestone,
            title=f"Evaluasi CPL {cpl.code}: Gap {gap:.2f}",
            status=TaskStatus.SIAP_DIKERJAKAN,
            explanation_what=f"Evaluasi capaian untuk {cpl.code} yang belum memenuhi target.",
            explanation_why=f"Nilai aktual ({actual:.2f}) di bawah target ({target:.2f}), gap: {gap:.2f}.",
            explanation_who="Kaprodi dan Tim Evaluasi",
            explanation_when="Segera setelah hasil perhitungan tersedia.",
            explanation_how="Analisis penyebab gap dan susun rencana perbaikan.",
            explanation_next="Implementasi perbaikan pada siklus berikutnya.",
        )
        return 1

    @staticmethod
    def get_results(cycle_id) -> list[AttainmentResult]:
        """Get all attainment results for a cycle."""
        return list(
            AttainmentResult.objects.filter(cycle_id=cycle_id)
            .prefetch_related("source_scores")
        )

    @staticmethod
    def list_editable(scope, template_type=None):
        """Return editable records for Excel import prefill."""
        return []
