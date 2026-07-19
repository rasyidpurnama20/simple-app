from django.contrib import admin

from obe.quality.models import ImprovementAction, IntegrityIssue, QualityCycle

admin.site.register([IntegrityIssue, ImprovementAction, QualityCycle])
