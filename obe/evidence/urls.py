from django.urls import path

from obe.evidence.views import download, issue_token

urlpatterns = [
    path("<uuid:public_id>/token/", issue_token, name="evidence-token"),
    path("<uuid:public_id>/download/", download, name="evidence-download"),
]
