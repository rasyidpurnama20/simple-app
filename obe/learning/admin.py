from django.contrib import admin

from obe.learning.models import (
    Attendance,
    CourseOffering,
    CourseOutcome,
    PerformanceIndicator,
    RPSFieldComment,
    RPSVersion,
    SubOutcome,
    WeeklyPlan,
)

admin.site.register(
    [
        CourseOffering,
        RPSVersion,
        CourseOutcome,
        SubOutcome,
        PerformanceIndicator,
        RPSFieldComment,
        WeeklyPlan,
        Attendance,
    ]
)
