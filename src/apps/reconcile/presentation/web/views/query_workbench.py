from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django_tables2.views import RequestConfig

from apps.identity.presentation.access import get_authorization_context
from apps.reconcile.application.services.query_workbench import QueryWorkbenchReader
from apps.reconcile.presentation.web.forms import QueryWorkbenchFilterForm
from apps.reconcile.presentation.web.tables import QueryWorkbenchTable, ValidationIssueWorkbenchTable
from apps.shared.context_processors import SiteDropdownHandler, StudyDropdownHandler
from apps.shared.navigation import get_default_authenticated_url, user_can_access_permission
from apps.shared.views import AuthenticateTemplateContextMixin
from apps.subject.presentation.web.views.base import SubjectAbstractVerifyStudy

VIEW_QUERY_PERMISSION = "reconcile.view_dataquery"
VIEW_INTERNAL_QUERY_THREAD_PERMISSION = "reconcile.view_internal_query_thread"
ANSWER_QUERY_PERMISSION = "QUERY.RESPOND"
RESOLVE_QUERY_PERMISSION = "QUERY.CLOSE"
CLOSE_QUERY_PERMISSION = "QUERY.CLOSE"
REOPEN_QUERY_PERMISSION = "QUERY.REOPEN"
CANCEL_QUERY_PERMISSION = "QUERY.CANCEL"
REOPEN_VALIDATION_ISSUE_PERMISSION = "VALIDATION_ISSUE.REOPEN"


class QueryWorkbenchView(AuthenticateTemplateContextMixin, SubjectAbstractVerifyStudy, TemplateView):
    permission_required = VIEW_QUERY_PERMISSION
    raise_exception = True
    layout_nav_key = "QUERIES"
    layout_breadcrumb_label = _("DATA QUERIES")
    template_name = "reconcile/query_workbench.html"
    reader_class = QueryWorkbenchReader
    paginate_by = 25

    def get_selected_site_id(self):
        return (
            SiteDropdownHandler(
                request=self.request,
                study_id=self.get_study_id(),
            )
            .build()
            .selected_id
        )

    def get(self, request, *args, **kwargs):
        path_study_id = self.get_study_id()
        resolved_study_id = StudyDropdownHandler(request=request).build().selected_id
        if path_study_id and resolved_study_id:
            if path_study_id == resolved_study_id:
                if request.GET.get("bucket") == "validation_issues" and not request.GET.get("source"):
                    query_params = request.GET.copy()
                    query_params.pop("bucket", None)
                    query_params["source"] = "validation_issues"
                    return redirect(f"{request.path}?{query_params.urlencode()}")
                if not request.GET:
                    return redirect(f"{request.path}?{urlencode({'status': 'open', 'assigned_to_me': 'on', 'opened_by_me': 'on'})}")
                return super().get(request, *args, **kwargs)
            return redirect(reverse("reconcile:query_workbench", kwargs={"study_id": resolved_study_id}))
        return redirect(get_default_authenticated_url(request))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_params = self.request.GET.copy()
        if not filter_params:
            filter_params["status"] = "open"
            filter_params["assigned_to_me"] = "on"
            filter_params["opened_by_me"] = "on"
        filter_form = QueryWorkbenchFilterForm(filter_params)
        filter_form.is_valid()
        cleaned = filter_form.cleaned_data
        source = cleaned.get("source") or ""
        reader_bucket = "validation_issues" if source == "validation_issues" else "all"
        selected_site_id = self.get_selected_site_id()
        can_view_internal_thread = user_can_access_permission(
            self.request.user,
            VIEW_INTERNAL_QUERY_THREAD_PERMISSION,
            study_id=self.get_study_id(),
            site_id=selected_site_id,
        )
        result = self.reader_class().read(
            study_id=self.get_study_id(),
            site_id=selected_site_id,
            current_user_id=self.request.user.pk,
            can_view_internal_thread=can_view_internal_thread,
            bucket=reader_bucket,
            search=cleaned.get("search") or "",
            status=cleaned.get("status") or "",
            severity=cleaned.get("severity") or "",
            source="" if source == "validation_issues" else source,
            blocking=cleaned.get("blocking") or "",
            assigned_to_id=self.request.user.pk if cleaned.get("assigned_to_me") else None,
            opened_by_id=self.request.user.pk if cleaned.get("opened_by_me") else None,
            sort=self.request.GET.get("sort") or "-last_activity_at",
        )
        table = QueryWorkbenchTable(result.items)
        validation_issue_table = ValidationIssueWorkbenchTable(result.validation_issues)
        empty_text = _("No data queries match the current filters.") if filter_params else _("No data queries found for the selected study/site.")
        table.empty_text = empty_text
        validation_issue_table.empty_text = _("No validation issues match the current filters.")
        RequestConfig(self.request, paginate={"per_page": self.paginate_by}).configure(table)
        RequestConfig(self.request, paginate={"per_page": self.paginate_by}).configure(validation_issue_table)
        context.update(
            {
                "filter_form": filter_form,
                "summary": result.summary,
                "table": table,
                "validation_issue_table": validation_issue_table,
                "show_validation_issues": source == "validation_issues",
                "empty_text": empty_text,
                **self._query_action_permissions(selected_site_id=selected_site_id),
            }
        )
        return context

    def _query_action_permissions(self, *, selected_site_id: int | None):
        return {
            "can_answer_dataquery": user_can_access_permission(
                self.request.user,
                ANSWER_QUERY_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
            "can_resolve_dataquery": user_can_access_permission(
                self.request.user,
                RESOLVE_QUERY_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
            "can_close_dataquery": user_can_access_permission(
                self.request.user,
                CLOSE_QUERY_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
            "can_reopen_dataquery": user_can_access_permission(
                self.request.user,
                REOPEN_QUERY_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
            "can_cancel_dataquery": user_can_access_permission(
                self.request.user,
                CANCEL_QUERY_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
            "can_reopen_validation_issue": user_can_access_permission(
                self.request.user,
                REOPEN_VALIDATION_ISSUE_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
        }

class QueryDetailView(AuthenticateTemplateContextMixin, SubjectAbstractVerifyStudy, TemplateView):
    permission_required = VIEW_QUERY_PERMISSION
    authorization_scope = "STUDY_SITE"
    require_site_context = True
    raise_exception = True
    layout_nav_key = "QUERIES"
    layout_breadcrumb_label = _("DATA QUERIES")
    template_name = "reconcile/query_detail.html"
    reader_class = QueryWorkbenchReader

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_site_id = get_authorization_context(self.request).study_site_id
        can_view_internal_thread = user_can_access_permission(
            self.request.user,
            VIEW_INTERNAL_QUERY_THREAD_PERMISSION,
            study_id=self.get_study_id(),
            site_id=selected_site_id,
        )
        detail = self.reader_class().read_detail(
            query_id=self.kwargs["query_id"],
            can_view_internal_thread=can_view_internal_thread,
        )
        if detail is None:
            raise Http404
        query, threads = detail
        if query.study_id != self.get_study_id():
            raise Http404
        context.update(
            {
                "query": query,
                "threads": threads,
                "back_url": reverse("reconcile:query_workbench", kwargs={"study_id": self.get_study_id()}),
                "layout_breadcrumb_label": _("Data Query DQ-%(query_id)s") % {"query_id": query.query_id},
                "layout_detail_meta_items": (
                    {
                        "label": _("Status"),
                        "value": str(query.status or "").title() or "—",
                    },
                ),
                **self._query_action_permissions(selected_site_id=query.site_id),
            }
        )
        return context

    def _query_action_permissions(self, *, selected_site_id: int | None):
        return {
            "can_answer_dataquery": user_can_access_permission(
                self.request.user,
                ANSWER_QUERY_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
            "can_resolve_dataquery": user_can_access_permission(
                self.request.user,
                RESOLVE_QUERY_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
            "can_close_dataquery": user_can_access_permission(
                self.request.user,
                CLOSE_QUERY_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
            "can_reopen_dataquery": user_can_access_permission(
                self.request.user,
                REOPEN_QUERY_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
            "can_cancel_dataquery": user_can_access_permission(
                self.request.user,
                CANCEL_QUERY_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
            "can_reopen_validation_issue": user_can_access_permission(
                self.request.user,
                REOPEN_VALIDATION_ISSUE_PERMISSION,
                study_id=self.get_study_id(),
                site_id=selected_site_id,
            ),
        }
