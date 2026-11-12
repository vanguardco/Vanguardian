import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.datacapture.public import get_page_state_contexts
from apps.identity.presentation.mixins import ContextPermissionRequiredMixin
from apps.reconcile.application import ReconcileDataQueryWriteService
from apps.shared.navigation import user_can_access_permission
from apps.subject.presentation.web.views.base import SubjectAbstractVerifyStudy

ACTION_PERMISSION_BY_ACTION = {
    "reopen": "VALIDATION_ISSUE.REOPEN",
}
ALLOWED_STATUSES_BY_ACTION = {
    "reopen": {"ACKNOWLEDGED"},
}


def _json_body(raw_body: bytes) -> dict:
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


@method_decorator(csrf_exempt, name="dispatch")
class ValidationIssueLifecycleActionAPIView(
    LoginRequiredMixin,
    ContextPermissionRequiredMixin,
    SubjectAbstractVerifyStudy,
    View,
):
    permission_required = "reconcile.view_dataquery"
    authorization_scope = "STUDY_SITE"
    require_site_context = True
    raise_exception = True

    def post(self, request, *args, **kwargs):
        action = str(kwargs["action"] or "").strip().lower()
        permission_code = ACTION_PERMISSION_BY_ACTION.get(action)
        if permission_code is None:
            return JsonResponse({"error": ["Unsupported validation issue action."]}, status=404)

        service = ReconcileDataQueryWriteService()
        scope = service.validation_issue_action_scope(issue_id=int(kwargs["issue_id"]))
        if scope is None:
            return JsonResponse({"error": ["Validation issue not found."]}, status=404)
        context = get_page_state_contexts(page_state_ids=[int(scope["page_state_id"])]).get(int(scope["page_state_id"]))
        study_id = int(kwargs["study_id"])
        if context is None or int(getattr(context, "study_id", 0) or 0) != study_id:
            return JsonResponse({"error": ["Validation issue not found."]}, status=404)

        if not user_can_access_permission(
            request.user,
            permission_code,
            study_id=study_id,
            site_id=getattr(context, "site_id", None),
        ):
            return JsonResponse({"error": ["Permission denied."]}, status=403)

        current_status = str(scope.get("status") or "").strip().upper()
        if current_status not in ALLOWED_STATUSES_BY_ACTION[action]:
            return JsonResponse({"error": ["Action is not allowed for current validation issue status."]}, status=400)

        try:
            result = service.reopen_validation_issue(
                issue_id=int(scope["issue_id"]),
                reason=str(_json_body(request.body).get("message_text") or "").strip(),
                actor_user_id=getattr(request.user, "id", None),
            )
        except ValueError as exc:
            return JsonResponse({"error": [str(exc)]}, status=400)
        if not result.get("changed"):
            return JsonResponse(
                {"error": ["Action is not allowed for current validation issue status."]},
                status=400,
            )
        return JsonResponse(
            {
                "ok": True,
                "issue_id": int(kwargs["issue_id"]),
                "status": result.get("status") or "ACKNOWLEDGEMENT_REQUIRED",
            }
        )


__all__ = ["ValidationIssueLifecycleActionAPIView"]
