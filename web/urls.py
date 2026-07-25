"""URL routes for the presentation (web) module."""

from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("switch-role/", views.switch_role, name="switch_role"),
]
