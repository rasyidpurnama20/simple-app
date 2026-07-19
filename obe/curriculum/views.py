from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render

from obe.curriculum.models import CurriculumVersion
from obe.curriculum.services import allocation_report, catalog_report, traceability_report


@login_required
def catalog(request):
    curriculum = (
        CurriculumVersion.objects.annotate(
            outcome_count=Count("outcomes", distinct=True),
            course_count=Count("courses", distinct=True),
        )
        .exclude(status="archived")
        .order_by("-cohort_from", "-version")
        .first()
    )
    courses = []
    required_credits = elective_credits = 0
    catalog_validation = allocation_validation = traceability_validation = None
    if curriculum:
        courses = curriculum.courses.order_by("recommended_semester", "code")
        required_credits = (
            courses.filter(required=True).aggregate(total=Sum("credits"))["total"] or 0
        )
        elective_credits = (
            courses.filter(required=False).aggregate(total=Sum("credits"))["total"] or 0
        )
        catalog_validation = catalog_report(curriculum)
        allocation_validation = allocation_report(curriculum)
        traceability_validation = traceability_report(curriculum)
    return render(
        request,
        "curriculum/catalog.html",
        {
            "curriculum": curriculum,
            "courses": courses,
            "required_credits": required_credits,
            "elective_credits": elective_credits,
            "catalog_validation": catalog_validation,
            "allocation_validation": allocation_validation,
            "traceability_validation": traceability_validation,
        },
    )
