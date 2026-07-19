from django.urls import path

from obe.academic_lifecycle.views import my_tasks

urlpatterns = [path("", my_tasks, name="my_tasks")]
