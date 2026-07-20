from django.urls import path

from obe.analytics.views import SemanticAnalyticsView, TraceabilityView

urlpatterns = [
    path("semantic/", SemanticAnalyticsView.as_view(), name="semantic-analytics"),
    path(
        "attainment/<uuid:snapshot_id>/trace/",
        TraceabilityView.as_view(),
        name="attainment-trace",
    ),
]
