from django.contrib import admin

from obe.secure_exam.models import Exam, ExamResponse, ExamSession

admin.site.register([Exam, ExamSession, ExamResponse])
