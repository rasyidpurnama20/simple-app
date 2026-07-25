"""Attainment_Engine models.

Implements CalculationFormula and AttainmentResult (Requirements 11.2-11.4, 18.2).
"""

from __future__ import annotations

from django.db import models


class FormulaLevel(models.TextChoices):
    """Aggregation level of a calculation formula."""

    CRITERION = "criterion", "Criterion"
    INDICATOR = "indicator", "Indicator"
    SUBCPMK = "subcpmk", "Sub-CPMK"
    CPMK = "cpmk", "CPMK"
    CPL = "cpl", "CPL"


class CalculationFormula(models.Model):
    """A named, versioned calculation formula for attainment aggregation.

    Stored as versioned configuration (Requirement 18.2). Each formula defines
    how scores are aggregated at a specific level.
    """

    name = models.CharField(max_length=128)
    version = models.PositiveIntegerField(default=1)
    level = models.CharField(max_length=16, choices=FormulaLevel.choices)
    definition = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Calculation Formula"
        verbose_name_plural = "Calculation Formulas"
        ordering = ["name", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "version"],
                name="uniq_formula_name_version",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"


class AttainmentResult(models.Model):
    """The result of an attainment calculation for a specific outcome.

    Records formula identity, actual/target/gap, and traceability to source
    scores (Requirements 11.2, 11.3, 11.4).
    """

    cycle = models.ForeignKey(
        "timeline.OBECycle",
        on_delete=models.CASCADE,
        related_name="attainment_results",
        null=True,
        blank=True,
    )
    outcome_ref = models.CharField(max_length=128)
    actual_value = models.DecimalField(max_digits=6, decimal_places=2)
    target_value = models.DecimalField(max_digits=6, decimal_places=2)
    gap = models.DecimalField(max_digits=6, decimal_places=2)
    formula_name = models.CharField(max_length=128)
    formula_version = models.PositiveIntegerField()
    source_scores = models.ManyToManyField(
        "rps.Score",
        related_name="attainment_results",
        blank=True,
    )
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Attainment Result"
        verbose_name_plural = "Attainment Results"
        ordering = ["-created_time"]

    def __str__(self) -> str:
        return f"{self.outcome_ref}: {self.actual_value}/{self.target_value}"
