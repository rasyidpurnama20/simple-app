"""URL routes for the presentation (web) module.

Registers routes for all five workspaces (Requirement 16.1):
Home, Timeline, Curriculum, Learning, Attainment & Quality.
"""

from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    # Home workspace
    path("", views.home, name="home"),
    path("switch-role/", views.switch_role, name="switch_role"),

    # Timeline workspace
    path("timeline/", views.timeline_workspace, name="timeline"),
    path("timeline/cycles/", views.timeline_cycles, name="timeline_cycles"),
    path("timeline/templates/", views.timeline_templates, name="timeline_templates"),
    path("timeline/<int:pk>/", views.timeline_detail, name="timeline_detail"),

    # Curriculum workspace
    path("curriculum/", views.curriculum_workspace, name="curriculum"),
    path("curriculum/create/", views.curriculum_create, name="curriculum_create"),
    path("curriculum/<int:pk>/activate/", views.curriculum_activate, name="curriculum_activate"),
    path("curriculum/<int:pk>/cpls/", views.curriculum_cpls, name="curriculum_cpls"),
    path("curriculum/<int:pk>/cpls/add/", views.add_cpl, name="add_cpl"),
    path("curriculum/cpl/<int:cpl_id>/indicator/add/", views.add_cpl_indicator, name="add_cpl_indicator"),
    path("curriculum/<int:pk>/courses/", views.curriculum_courses, name="curriculum_courses"),
    path("curriculum/<int:pk>/courses/add/", views.add_course, name="add_course"),
    path("curriculum/<int:pk>/map/", views.curriculum_map_course, name="curriculum_map_course"),

    # Learning workspace (RPS authoring)
    path("learning/", views.learning_workspace, name="learning"),
    path("learning/rps/create/", views.rps_create, name="rps_create"),
    path("learning/rps/<int:pk>/", views.rps_detail, name="rps_detail"),
    path("learning/rps/<int:pk>/cpmk/", views.rps_add_cpmk, name="rps_add_cpmk"),
    path("learning/rps/<int:pk>/instrument/", views.rps_add_instrument, name="rps_add_instrument"),
    path("learning/rps/<int:pk>/rubric/", views.rps_define_rubric, name="rps_define_rubric"),
    path("learning/rps/<int:pk>/submit/", views.rps_submit, name="rps_submit"),

    # Attainment & Quality workspace
    path("attainment/", views.attainment_workspace, name="attainment"),
    path("attainment/calculate/<int:cycle_id>/", views.attainment_calculate, name="attainment_calculate"),
]
