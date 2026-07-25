"""URL routes for the excel_import module."""

from django.urls import path

from . import views

app_name = "excel_import"

urlpatterns = [
    path("", views.excel_import_workspace, name="workspace"),
    path("generate/", views.generate_template, name="generate"),
    path("upload/", views.upload_and_dry_run, name="upload"),
    path("commit/", views.commit_batch, name="commit"),
]
