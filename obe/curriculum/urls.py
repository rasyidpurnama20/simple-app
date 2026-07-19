from django.urls import path

from obe.curriculum.views import catalog

urlpatterns = [path("", catalog, name="curriculum_catalog")]
