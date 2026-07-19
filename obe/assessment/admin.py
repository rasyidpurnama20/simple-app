from django.contrib import admin

from obe.assessment.models import AssessmentInstrument, AttainmentSnapshot, Score, Submission

admin.site.register([AssessmentInstrument, Submission, Score, AttainmentSnapshot])
