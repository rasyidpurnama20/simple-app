from django.contrib import admin

from obe.quality.models import (
    ImprovementAction,
    IntegrityIssue,
    IntegrityValidationRun,
    QualityCycle,
)

admin.site.register([IntegrityIssue, IntegrityValidationRun, ImprovementAction, QualityCycle])
