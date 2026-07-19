from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from obe.academic_lifecycle.models import StudentProfile, TaskInstance


@login_required
def my_tasks(request):
    tasks = TaskInstance.objects.filter(owner=request.user).order_by("due_at")[:50]
    template = "partials/tasks.html" if request.headers.get("HX-Request") else "tasks.html"
    return render(request, template, {"tasks": tasks})


@login_required
def my_progress(request):
    try:
        profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        profile = None
    results = []
    credits = 0
    gpa = None
    if profile:
        queryset = profile.results.order_by("semester", "academic_year", "course_public_id")
        results = list(queryset)
        Course = apps.get_model("curriculum", "Course")
        course_labels = {
            str(public_id): f"{code} · {name}"
            for public_id, code, name in Course.objects.filter(
                public_id__in=[result.course_public_id for result in results]
            ).values_list("public_id", "code", "name")
        }
        for result in results:
            result.course_label = course_labels.get(
                str(result.course_public_id), str(result.course_public_id)
            )
        credits = queryset.filter(passed=True).aggregate(total=Sum("credits"))["total"] or 0
        weighted = sum(
            result.credits * result.grade_point
            for result in results
            if result.grade_point is not None
        )
        attempted = sum(result.credits for result in results if result.grade_point is not None)
        gpa = weighted / attempted if attempted else None
    return render(
        request,
        "academic_lifecycle/progress.html",
        {"profile": profile, "results": results, "credits": credits, "gpa": gpa},
    )
