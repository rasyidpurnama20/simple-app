from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from obe.academic_lifecycle.models import TaskInstance


@login_required
def my_tasks(request):
    tasks = TaskInstance.objects.filter(owner=request.user).order_by("due_at")[:50]
    template = "partials/tasks.html" if request.headers.get("HX-Request") else "tasks.html"
    return render(request, template, {"tasks": tasks})
