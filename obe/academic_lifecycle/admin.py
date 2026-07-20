from django.contrib import admin

from obe.academic_lifecycle.models import (
    AcademicResult,
    AcademicStatus,
    EnrollmentPlan,
    LifecycleApplication,
    LifecycleConfiguration,
    Notification,
    StudentProfile,
    TaskInstance,
)

admin.site.register(
    [
        StudentProfile,
        AcademicStatus,
        EnrollmentPlan,
        AcademicResult,
        TaskInstance,
        Notification,
        LifecycleApplication,
        LifecycleConfiguration,
    ]
)
