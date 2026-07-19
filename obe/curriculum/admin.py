from django.contrib import admin

from obe.curriculum.models import Course, CurriculumEdge, CurriculumVersion, Outcome

admin.site.register([CurriculumVersion, Outcome, Course, CurriculumEdge])
