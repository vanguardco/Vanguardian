from django.urls import path

from apps.reconcile.presentation.api.views import (
    QueryLifecycleActionAPIView,
    ValidationIssueLifecycleActionAPIView,
)

app_name = "reconcile_api"

urlpatterns = [
    path(
        "studies/<int:study_id>/queries/<int:query_id>/<str:action>/",
        QueryLifecycleActionAPIView.as_view(),
        name="query_action",
    ),
    path(
        "studies/<int:study_id>/validation-issues/<int:issue_id>/<str:action>/",
        ValidationIssueLifecycleActionAPIView.as_view(),
        name="validation_issue_action",
    ),
]
