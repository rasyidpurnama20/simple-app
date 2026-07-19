from django.contrib import admin

from obe.learning.models import Attendance, CourseOffering, RPSVersion, WeeklyPlan

admin.site.register([CourseOffering, RPSVersion, WeeklyPlan, Attendance])
