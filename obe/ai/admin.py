from django.contrib import admin

from obe.ai.models import AIRun, PromptTemplate

admin.site.register([PromptTemplate, AIRun])
