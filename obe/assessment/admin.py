from django.contrib import admin

from obe.assessment.models import (
    AssessmentInstrument,
    AssessmentItem,
    AttainmentSnapshot,
    CompetencyScale,
    CriterionScore,
    ExamEquivalenceReview,
    ParallelExamPolicy,
    PerformanceLevel,
    QuestionSetVersion,
    Rubric,
    RubricCriterion,
    Score,
    ScoreRevision,
    Submission,
    SubmissionGroup,
)

admin.site.register(
    [
        AssessmentInstrument,
        AssessmentItem,
        Rubric,
        RubricCriterion,
        PerformanceLevel,
        Submission,
        SubmissionGroup,
        Score,
        ScoreRevision,
        CompetencyScale,
        ParallelExamPolicy,
        QuestionSetVersion,
        ExamEquivalenceReview,
        CriterionScore,
        AttainmentSnapshot,
    ]
)
