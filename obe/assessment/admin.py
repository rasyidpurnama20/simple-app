from django.contrib import admin

from obe.assessment.models import (
    AssessmentInstrument,
    AssessmentItem,
    AttainmentSnapshot,
    CriterionScore,
    PerformanceLevel,
    Rubric,
    RubricCriterion,
    Score,
    Submission,
)

admin.site.register(
    [
        AssessmentInstrument,
        AssessmentItem,
        Rubric,
        RubricCriterion,
        PerformanceLevel,
        Submission,
        Score,
        CriterionScore,
        AttainmentSnapshot,
    ]
)
