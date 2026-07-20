from django.contrib import admin

from obe.quality.models import (
    ImprovementAction,
    IntegrityIssue,
    IntegrityValidationRun,
    QualityCycle,
    QualityFinding,
    QualityStandard,
)

admin.site.register(
    [
        IntegrityIssue,
        IntegrityValidationRun,
        ImprovementAction,
        QualityCycle,
        QualityStandard,
        QualityFinding,
    ]
)
