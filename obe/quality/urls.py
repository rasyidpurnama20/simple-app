from django.urls import path

from obe.quality.views import (
    AcademicFeedbackCollectionView,
    AcademicFeedbackDetailView,
    PortfolioDetailView,
    QualityFindingListView,
    QualityReportDetailView,
)

urlpatterns = [
    path("portfolios/<uuid:public_id>/", PortfolioDetailView.as_view(), name="portfolio-detail"),
    path("findings/", QualityFindingListView.as_view(), name="quality-finding-list"),
    path("reports/<uuid:public_id>/", QualityReportDetailView.as_view(), name="quality-report"),
    path("feedback/", AcademicFeedbackCollectionView.as_view(), name="academic-feedback"),
    path(
        "feedback/<uuid:public_id>/",
        AcademicFeedbackDetailView.as_view(),
        name="academic-feedback-detail",
    ),
]
