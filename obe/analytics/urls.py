from django.urls import path

from obe.analytics.views import SemanticAnalyticsView

urlpatterns = [path("semantic/", SemanticAnalyticsView.as_view(), name="semantic-analytics")]
