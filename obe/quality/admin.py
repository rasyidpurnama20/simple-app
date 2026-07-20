from django.contrib import admin

from obe.quality.models import (
    AcademicFeedback,
    ImprovementAction,
    IntegrityIssue,
    IntegrityValidationRun,
    PortfolioSnapshot,
    QualityCycle,
    QualityFinding,
    QualityReport,
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
        PortfolioSnapshot,
        QualityReport,
        AcademicFeedback,
    ]
)
