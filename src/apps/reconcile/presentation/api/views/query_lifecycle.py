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
    "answer": "QUERY.RESPOND",
    "request_clarification": "QUERY.RETURN",
    "resolve": "QUERY.CLOSE",
    "close": "QUERY.CLOSE",
    "reopen": "QUERY.REOPEN",
    "cancel": "QUERY.CANCEL",
}

ALLOWED_STATUSES_BY_ACTION = {
    "answer": {"open", "answered"},
    "request_clarification": {"answered"},
    "resolve": {"answered"},
    "close": {"resolved"},
    "reopen": {"resolved", "closed"},
    "cancel": {"open"},
}


def _json_body(raw_body: bytes) -> dict:
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


@method_decorator(csrf_exempt, name="dispatch")
class QueryLifecycleActionAPIView(LoginRequiredMixin, ContextPermissionRequiredMixin, SubjectAbstractVerifyStudy, View):
    permission_required = "reconcile.view_dataquery"
    authorization_scope = "STUDY_SITE"
    require_site_context = True
    raise_exception = True

    def post(self, request, *args, **kwargs):
        action = str(kwargs["action"] or "").strip().lower()
        permission_code = ACTION_PERMISSION_BY_ACTION.get(action)
        if permission_code is None:
            return JsonResponse({"error": ["Unsupported query action."]}, status=404)

        service = ReconcileDataQueryWriteService()
        scope = service.query_action_scope(dataquery_id=int(kwargs["query_id"]))
        if scope is None:
            return JsonResponse({"error": ["Query not found."]}, status=404)
        context = get_page_state_contexts(page_state_ids=[int(scope["page_state_id"])]).get(int(scope["page_state_id"]))
        study_id = int(kwargs["study_id"])
        if context is None or int(getattr(context, "study_id", 0) or 0) != study_id:
            return JsonResponse({"error": ["Query not found."]}, status=404)

        if not user_can_access_permission(
            request.user,
            permission_code,
            study_id=study_id,
            site_id=getattr(context, "site_id", None),
        ):
            return JsonResponse({"error": ["Permission denied."]}, status=403)

        current_status = str(scope.get("status") or "").strip().lower()
        if current_status not in ALLOWED_STATUSES_BY_ACTION[action]:
            return JsonResponse({"error": ["Action is not allowed for current query status."]}, status=400)

        message_text = str(_json_body(request.body).get("message_text") or "").strip()
        try:
            result = self._execute_action(
                action=action,
                scope=scope,
                message_text=message_text,
                actor_user_id=getattr(request.user, "id", None),
                service=service,
            )
        except ValueError as exc:
            return JsonResponse({"error": [str(exc)]}, status=400)
        if not result.get("changed"):
            return JsonResponse({"error": ["Action is not allowed for current query status."]}, status=400)
        return JsonResponse(
            {
                "ok": True,
                "query_id": int(kwargs["query_id"]),
                "status": result.get("status") or action,
                "message_text": result.get("message_text") or "",
                "message_type": result.get("message_type") or "",
            }
        )

    @staticmethod
    def _execute_action(
        *,
        action: str,
        scope: dict,
        message_text: str,
        actor_user_id: int | None,
        service: ReconcileDataQueryWriteService,
    ):
        command_kwargs = {
            "dataquery_id": int(scope["dataquery_id"]),
            "page_state_id": int(scope["page_state_id"]),
            "field_template_id": scope.get("field_template_id"),
            "message_text": message_text,
            "actor_user_id": actor_user_id,
        }
        if action == "answer":
            return service.reply_to_query(**command_kwargs)
        if action == "request_clarification":
            return service.request_clarification(**command_kwargs)
        if action == "resolve":
            return service.resolve_query(**command_kwargs)
        if action == "close":
            return service.close_resolved_query(**command_kwargs)
        if action == "reopen":
            return service.reopen_query(**command_kwargs)
        if action == "cancel":
            return service.cancel_dataquery(**command_kwargs)
        raise ValueError("Unsupported query action.")
