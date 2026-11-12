from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from apps.reconcile.application import ReconcileDataQueryReadService
from apps.reconcile.application.services.query_workbench import QueryWorkbenchReader
from apps.reconcile.infrastructure.repositories.dataquery_read import DjangoReconcileDataQueryReadRepository
from apps.reconcile.presentation.api.views import (
    QueryLifecycleActionAPIView,
    ValidationIssueLifecycleActionAPIView,
)
from apps.reconcile.presentation.web.forms import QueryWorkbenchFilterForm
from apps.reconcile.presentation.web.views import QueryWorkbenchView
from apps.shared.context_processors import shared_select_options


class QueryWorkbenchReaderTests(SimpleTestCase):
    def test_dataquery_read_service_exposes_workbench_summary(self):
        repository = _WorkbenchRepository()

        result = ReconcileDataQueryReadService(repository=repository).summarize_workbench(
            page_state_ids=(10,),
        )

        self.assertEqual(result["open"], 1)
        self.assertEqual(result["validation_issues_open"], 1)

    def test_pending_with_maps_status_to_responsible_party(self):
        self.assertEqual(QueryWorkbenchReader.pending_with("open"), "Site / Data Entry")
        self.assertEqual(QueryWorkbenchReader.pending_with("answered"), "CRA / Data Manager")
        self.assertEqual(QueryWorkbenchReader.pending_with("resolved"), "Data Manager / Close")
        self.assertEqual(QueryWorkbenchReader.pending_with("closed"), "—")

    def test_context_search_supports_subject_screening_and_randomization_codes(self):
        contexts = {
            10: SimpleNamespace(
                subject_code="SUBJ-001",
                screening_code="SCR-001",
                randomization_code="RND-001",
                event_code="VISIT1",
                event_label="Visit 1",
                crf_page_label="Vitals",
            ),
            20: SimpleNamespace(
                subject_code="SUBJ-002",
                screening_code="SCR-002",
                randomization_code="RND-002",
                event_code="VISIT2",
                event_label="Visit 2",
                crf_page_label="Labs",
            ),
        }
        reader = QueryWorkbenchReader(repository=_WorkbenchRepository())

        for search, expected_page_state_id in (
            ("SUBJ-002", 20),
            ("SCR-001", 10),
            ("RND-002", 20),
        ):
            with self.subTest(search=search):
                filtered, query_search = reader._filter_contexts_for_search(contexts, search)
                self.assertEqual(set(filtered), {expected_page_state_id})
                self.assertEqual(query_search, "")

    def test_validation_issue_search_uses_identifier_matched_contexts(self):
        contexts = {
            10: SimpleNamespace(
                page_state_id=10,
                study_id=1,
                site_id=2,
                subject_id=3,
                subject_code="SUBJ-001",
                screening_code="SCR-001",
                randomization_code="RND-001",
                event_instance_id=4,
                event_code="VISIT1",
                event_label="Visit 1",
                crf_page_label="Vitals",
                page_template_id=5,
            )
        }
        repository = _WorkbenchRepository()
        with (
            patch(
                "apps.datacapture.public.list_page_state_contexts_for_study_site",
                return_value=contexts,
            ),
            patch("apps.identity.public.get_user_display_map", return_value={8: "CRA Reviewer"}),
        ):
            result = QueryWorkbenchReader(repository=repository).read(
                study_id=1,
                site_id=2,
                current_user_id=9,
                can_view_internal_thread=False,
                bucket="validation_issues",
                search="RND-001",
            )

        self.assertEqual(repository.last_validation_issue_kwargs["search"], "")
        self.assertEqual(len(result.validation_issues), 1)

    def test_reader_builds_summary_items_and_validation_issues_from_scoped_context(self):
        contexts = {
            10: SimpleNamespace(
                page_state_id=10,
                study_id=1,
                site_id=2,
                subject_id=3,
                subject_code="SUBJ-001",
                screening_code="SCR-001",
                event_instance_id=4,
                event_code="VISIT1",
                event_label="Visit 1",
                crf_page_label="Vitals",
                page_template_id=5,
                event_form_binding_id=680,
            )
        }
        repository = _WorkbenchRepository()
        with (
            patch(
                "apps.datacapture.public.list_page_state_contexts_for_study_site",
                return_value=contexts,
            ),
            patch(
                "apps.identity.public.get_user_display_map",
                return_value={8: "CRA Reviewer", 9: "Site User"},
            ),
        ):
            result = QueryWorkbenchReader(repository=repository).read(
                study_id=1,
                site_id=2,
                current_user_id=9,
                can_view_internal_thread=False,
                bucket="validation_issues",
            )

        self.assertEqual(result.summary.open, 1)
        self.assertEqual(result.summary.awaiting_site_response, 2)
        self.assertEqual(result.summary.awaiting_review, 1)
        self.assertEqual(result.summary.blocking_open, 1)
        self.assertEqual(result.summary.closed, 0)
        self.assertEqual(result.items, [])
        self.assertEqual(result.validation_issues[0].subject_code, "SUBJ-001")
        self.assertEqual(result.validation_issues[0].field_label, "Reticulocyte % (RET%)")
        self.assertEqual(
            result.validation_issues[0].review_focus_url,
            "/studies/1/subjects/3/?mode=verification&event=4&form=680",
        )
        self.assertEqual(result.validation_issues[0].acknowledged_by_display, "CRA Reviewer")

    def test_reader_maps_query_row_context_and_reply_count(self):
        contexts = {
            10: SimpleNamespace(
                page_state_id=10,
                study_id=1,
                site_id=2,
                subject_id=3,
                subject_code="SUBJ-001",
                screening_code="SCR-001",
                event_instance_id=4,
                event_code="VISIT1",
                event_label="Visit 1",
                crf_page_label="Vitals",
                page_template_id=5,
            )
        }
        repository = _WorkbenchRepository(
            rows=[
                {
                    "query_id": 11,
                    "page_state_id": 10,
                    "status": "answered",
                    "source": "manual",
                    "query_type": "manual",
                    "severity": "major",
                    "is_blocking": True,
                    "question_text": "Please confirm the weight value",
                    "resolution_note": "",
                    "field_path": "$.weight",
                    "value_snapshot": "72",
                    "opened_at": None,
                    "answered_at": None,
                    "resolved_at": None,
                    "closed_at": None,
                    "last_activity_at": None,
                    "reply_count": 3,
                    "assigned_to_id": 8,
                    "opened_by_id": 9,
                    "field_label": "Weight",
                }
            ]
        )
        with (
            patch(
                "apps.datacapture.public.list_page_state_contexts_for_study_site",
                return_value=contexts,
            ),
            patch(
                "apps.identity.public.get_user_display_map",
                return_value={8: "CRA Reviewer", 9: "Site User"},
            ),
        ):
            result = QueryWorkbenchReader(repository=repository).read(
                study_id=1,
                site_id=2,
                current_user_id=9,
                can_view_internal_thread=False,
                bucket="awaiting_review",
                assigned_to_id=9,
                opened_by_id=9,
            )

        self.assertEqual(repository.last_query_kwargs["bucket"], "awaiting_review")
        self.assertEqual(repository.last_query_kwargs["assigned_to_id"], 9)
        self.assertEqual(repository.last_query_kwargs["opened_by_id"], 9)
        self.assertEqual(result.items[0].pending_with, "CRA / Data Manager")
        self.assertEqual(result.items[0].reply_count, 3)
        self.assertEqual(result.items[0].subject_code, "SUBJ-001")
        self.assertEqual(result.items[0].subject_display_code, "SUBJ-001")
        self.assertEqual(result.items[0].assigned_to_display, "CRA Reviewer")
        self.assertEqual(result.items[0].opened_by_display, "Site User")
        self.assertEqual(result.items[0].field_label_or_path, "Weight")
        self.assertEqual(
            result.items[0].review_focus_url,
            "/studies/1/subjects/3/?mode=verification&event=4&form=5",
        )

    def test_reader_subject_display_falls_back_to_screening_code(self):
        contexts = {
            10: SimpleNamespace(
                page_state_id=10,
                study_id=1,
                site_id=2,
                subject_id=3,
                subject_code="",
                screening_code="SCR-001",
                event_instance_id=4,
                event_code="VISIT1",
                event_label="Visit 1",
                crf_page_label="Vitals",
                page_template_id=5,
            )
        }
        repository = _WorkbenchRepository(rows=[_query_row()])
        with (
            patch(
                "apps.datacapture.public.list_page_state_contexts_for_study_site",
                return_value=contexts,
            ),
            patch("apps.identity.public.get_user_display_map", return_value={}),
        ):
            result = QueryWorkbenchReader(repository=repository).read(
                study_id=1,
                site_id=2,
                current_user_id=9,
                can_view_internal_thread=False,
            )

        self.assertEqual(result.items[0].subject_display_code, "SCR-001")

    def test_reader_maps_detail_thread_authors_to_display_name(self):
        contexts = {
            10: SimpleNamespace(
                page_state_id=10,
                study_id=1,
                site_id=2,
                subject_id=3,
                subject_code="SUBJ-001",
                screening_code="SCR-001",
                event_instance_id=4,
                event_code="VISIT1",
                event_label="Visit 1",
                crf_page_label="Vitals",
                page_template_id=5,
            )
        }
        repository = _WorkbenchRepository(
            rows=[_query_row()],
            threads=[
                {
                    "id": 301,
                    "message_text": "Please confirm",
                    "message_type": "comment",
                    "visibility": "site",
                    "source": "manual",
                    "author_id": 8,
                    "created_at": None,
                }
            ],
        )
        with (
            patch("apps.datacapture.public.get_page_state_contexts", return_value=contexts),
            patch(
                "apps.identity.public.get_user_display_map",
                return_value={8: "CRA Reviewer", 9: "Site User"},
            ),
        ):
            query, threads = QueryWorkbenchReader(repository=repository).read_detail(
                query_id=11,
                can_view_internal_thread=False,
            )

        self.assertEqual(query.assigned_to_display, "CRA Reviewer")
        self.assertEqual(threads[0].author_display, "CRA Reviewer")

    def test_repository_lists_query_threads_newest_first(self):
        queryset = _ThreadQuerySet(
            [
                {
                    "id": 301,
                    "message_text": "Latest",
                    "message_type": "comment",
                    "visibility": "site",
                    "source": "manual",
                    "author_id": 8,
                    "created_at": None,
                }
            ]
        )

        with patch(
            "apps.reconcile.infrastructure.repositories.dataquery_read.ReconcileQueryThread.objects.filter",
            return_value=queryset,
        ):
            threads = DjangoReconcileDataQueryReadRepository().list_query_threads(
                query_id=11,
                can_view_internal_thread=True,
            )

        self.assertEqual(queryset.ordered_by, ("-created_at", "-id"))
        self.assertEqual(threads[0]["message_text"], "Latest")

    def test_repository_counts_open_queries_assigned_to_user(self):
        manager = _DataQueryManagerStub(count=7)

        with patch(
            "apps.reconcile.infrastructure.repositories.dataquery_read.ReconcileDataQuery.objects",
            manager,
        ):
            count = DjangoReconcileDataQueryReadRepository().count_open_queries_assigned_to_user(
                page_state_ids=(10, 11),
                user_id=9,
            )

        self.assertEqual(count, 7)
        self.assertEqual(manager.filter_kwargs["page_state_id__in"], (10, 11))
        self.assertEqual(manager.filter_kwargs["assigned_to_id"], 9)
        self.assertEqual(manager.filter_kwargs["deleted"], False)
        self.assertEqual(manager.filter_kwargs["status"], "open")

    def test_repository_counts_open_queries_assigned_to_user_for_study_site(self):
        manager = _DataQueryManagerStub(count=5)

        with patch(
            "apps.reconcile.infrastructure.repositories.dataquery_read.ReconcileDataQuery.objects",
            manager,
        ):
            count = DjangoReconcileDataQueryReadRepository().count_open_queries_assigned_to_user_for_study_site(
                study_id=1,
                site_id=2,
                user_id=9,
            )

        self.assertEqual(count, 5)
        self.assertEqual(manager.filter_calls[0]["assigned_to_id"], 9)
        self.assertEqual(manager.filter_calls[0]["deleted"], False)
        self.assertEqual(manager.filter_calls[0]["status"], "open")
        self.assertEqual(manager.filter_calls[0]["page_state__deleted"], False)
        self.assertEqual(manager.filter_calls[0]["page_state__subject__study_id"], 1)
        self.assertEqual(manager.filter_calls[1]["page_state__subject__site_id"], 2)

    def test_read_service_delegates_assigned_open_query_count(self):
        repository = _ReadServiceRepositoryStub()

        count = ReconcileDataQueryReadService(repository=repository).count_open_queries_assigned_to_user(
            page_state_ids=(10,),
            user_id=9,
        )

        self.assertEqual(count, 4)
        self.assertEqual(
            repository.assigned_count_kwargs,
            {
                "page_state_ids": (10,),
                "user_id": 9,
            },
        )

    def test_read_service_delegates_assigned_open_query_count_for_study_site(self):
        repository = _ReadServiceRepositoryStub()

        count = ReconcileDataQueryReadService(repository=repository).count_open_queries_assigned_to_user_for_study_site(
            study_id=1,
            site_id=2,
            user_id=9,
        )

        self.assertEqual(count, 4)
        self.assertEqual(
            repository.assigned_count_for_study_site_kwargs,
            {
                "study_id": 1,
                "site_id": 2,
                "user_id": 9,
            },
        )

    def test_reconcile_application_uses_datacapture_public_contract(self):
        source = Path("src/apps/reconcile/application/services/query_workbench.py").read_text()

        self.assertIn("from apps.datacapture.public import", source)
        self.assertNotIn("apps.datacapture.models", source)
        self.assertNotIn("apps.datacapture.infrastructure", source)


class QueryWorkbenchFilterFormTests(SimpleTestCase):
    def test_search_placeholder_mentions_supported_subject_codes(self):
        form = QueryWorkbenchFilterForm()
        placeholder = form.fields["search"].widget.attrs["placeholder"]
        aria_label = form.fields["search"].widget.aria_label

        self.assertIn("subject", str(placeholder))
        self.assertIn("screening", str(placeholder))
        self.assertIn("randomization", str(placeholder))
        self.assertIn("randomization", str(aria_label))

    def test_validation_issues_is_available_as_source_filter(self):
        form = QueryWorkbenchFilterForm({"source": "validation_issues"})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["source"], "validation_issues")
        self.assertIn(
            ("validation_issues", "Validation Issues"),
            list(form.fields["source"].choices),
        )

    def test_current_user_filters_parse_to_booleans(self):
        form = QueryWorkbenchFilterForm({"assigned_to_me": "on", "opened_by_me": "on"})

        self.assertTrue(form.is_valid())
        self.assertTrue(form.cleaned_data["assigned_to_me"])
        self.assertTrue(form.cleaned_data["opened_by_me"])
        self.assertEqual(
            form.fields["assigned_to_me"].widget.attrs["class"],
            "query-workbench__toolbar-checkbox-input",
        )
        self.assertEqual(
            form.fields["opened_by_me"].widget.attrs["class"],
            "query-workbench__toolbar-checkbox-input",
        )

    def test_current_user_filters_unchecked_when_missing(self):
        form = QueryWorkbenchFilterForm({})

        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data["assigned_to_me"])
        self.assertFalse(form.cleaned_data["opened_by_me"])


class QueryWorkbenchTemplateAndViewBehaviorTests(SimpleTestCase):
    def test_legacy_validation_issue_bucket_redirects_to_source_filter(self):
        request = RequestFactory().get(
            "/studies/1/queries/",
            data={"bucket": "validation_issues", "search": "VI-1061"},
        )
        request.user = SimpleNamespace(pk=11, is_authenticated=True)

        with patch(
            "apps.reconcile.presentation.web.views.query_workbench.StudyDropdownHandler",
            return_value=_SharedDropdownHandler(selected_id=1),
        ):
            view = QueryWorkbenchView()
            view.setup(request, study_id=1)
            response = view.get(request, study_id=1)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "/studies/1/queries/?search=VI-1061&source=validation_issues",
        )

    def test_query_workbench_view_passes_current_user_id_for_user_filters(self):
        reader = _DummyWorkbenchReader()
        user = SimpleNamespace(
            pk=11,
            id=11,
            is_authenticated=True,
            has_perm=lambda permission: True,
            get_full_name=lambda: "Quality QA",
            get_username=lambda: "quality.qa",
            email="",
            phone_number="",
            is_staff=False,
            is_superuser=False,
        )

        request = RequestFactory().get(
            "/studies/1/queries/",
            data={"assigned_to_me": "on", "opened_by_me": "on"},
        )
        request.user = user
        request.COOKIES = {}

        with (
            patch(
                "apps.reconcile.presentation.web.views.query_workbench.SiteDropdownHandler",
                return_value=_WorkbenchSiteDropdownHandler(),
            ),
            patch(
                "apps.reconcile.presentation.web.views.query_workbench.QueryWorkbenchView.reader_class",
                return_value=reader,
            ),
            patch(
                "apps.reconcile.presentation.web.views.query_workbench.user_can_access_permission",
                return_value=True,
            ),
        ):
            view = QueryWorkbenchView()
            view.setup(request, study_id=1)
            view.get_context_data()

        self.assertEqual(reader.last_read_kwargs["assigned_to_id"], 11)
        self.assertEqual(reader.last_read_kwargs["opened_by_id"], 11)

    def test_query_workbench_template_has_checkbox_controls_and_auto_submit(self):
        template_source = Path("src/templates/reconcile/query_workbench.html").read_text()

        self.assertNotIn("query-workbench__buckets", template_source)
        self.assertNotIn("bucket_tabs", template_source)
        self.assertIn("query-workbench__toolbar-user-filters", template_source)
        self.assertIn("query-workbench__toolbar-checkbox", template_source)
        self.assertIn("toolbarForm.submit()", template_source)

    def test_validation_issue_source_renders_validation_issue_table(self):
        reader = _DummyWorkbenchReader()
        request = RequestFactory().get(
            "/studies/1/queries/",
            data={"source": "validation_issues"},
        )
        request.user = SimpleNamespace(
            pk=11,
            id=11,
            is_authenticated=True,
            has_perm=lambda permission: True,
            get_full_name=lambda: "Quality QA",
            get_username=lambda: "quality.qa",
            email="",
            phone_number="",
            is_staff=False,
            is_superuser=False,
        )
        request.COOKIES = {}

        with (
            patch(
                "apps.reconcile.presentation.web.views.query_workbench.SiteDropdownHandler",
                return_value=_WorkbenchSiteDropdownHandler(),
            ),
            patch(
                "apps.reconcile.presentation.web.views.query_workbench.QueryWorkbenchView.reader_class",
                return_value=reader,
            ),
            patch(
                "apps.reconcile.presentation.web.views.query_workbench.user_can_access_permission",
                return_value=True,
            ),
        ):
            view = QueryWorkbenchView()
            view.setup(request, study_id=1)
            context = view.get_context_data()

        self.assertEqual(reader.last_read_kwargs["bucket"], "validation_issues")
        self.assertEqual(reader.last_read_kwargs["source"], "")
        self.assertIs(context["show_validation_issues"], True)

    def test_validation_issue_actions_include_review_and_permission_gated_reopen(self):
        template_source = Path("src/templates/reconcile/includes/validation_issue_workbench_actions_cell.html").read_text()

        self.assertIn('data-query-action="reopen_validation_issue"', template_source)
        self.assertIn("can_reopen_validation_issue", template_source)
        self.assertIn('record.status == "ACKNOWLEDGED"', template_source)
        self.assertIn("record.review_focus_url", template_source)


class QueryWorkbenchRoutingTests(SimpleTestCase):
    def test_query_workbench_route_resolves(self):
        match = resolve(reverse("reconcile:query_workbench", kwargs={"study_id": 1}))

        self.assertEqual(match.func.view_class, QueryWorkbenchView)

    def test_query_lifecycle_api_route_resolves(self):
        match = resolve(
            reverse(
                "reconcile_api:query_action",
                kwargs={"study_id": 1, "query_id": 2, "action": "resolve"},
            )
        )

        self.assertEqual(match.func.view_class, QueryLifecycleActionAPIView)

    def test_validation_issue_lifecycle_api_route_resolves(self):
        match = resolve(
            reverse(
                "reconcile_api:validation_issue_action",
                kwargs={"study_id": 1, "issue_id": 7, "action": "reopen"},
            )
        )

        self.assertEqual(match.func.view_class, ValidationIssueLifecycleActionAPIView)

    def test_query_nav_is_rendered_after_subjects(self):
        layout_source = Path("src/templates/shared/_layout.html").read_text()

        subject_index = layout_source.index("ui_permissions.SUBJECT_VIEW")
        query_index = layout_source.index("ui_permissions.QUERIES_VIEW")
        sites_index = layout_source.index("ui_permissions.SITES_VIEW_LIST")
        self.assertLess(subject_index, query_index)
        self.assertLess(query_index, sites_index)

    def test_query_nav_renders_need_response_badge(self):
        layout_source = Path("src/templates/shared/_layout.html").read_text()

        self.assertIn("layout_queries_need_response_count", layout_source)
        self.assertIn("top-nav__badge", layout_source)
        self.assertIn("queries need your response", layout_source)

    def test_query_detail_uses_shared_dashboard_breadcrumb(self):
        detail_source = Path("src/templates/reconcile/query_detail.html").read_text()

        self.assertIn("block dashboard_breadcrumb_prefix", detail_source)
        self.assertIn("dashboard-breadcrumb__back", detail_source)
        self.assertNotIn("query-detail__header", detail_source)
        self.assertIn("query-detail__field-alias", detail_source)
        self.assertIn("query.review_focus_url", detail_source)
        self.assertIn("request_clarification", detail_source)
        self.assertIn("Request Clarification", detail_source)
        self.assertIn('action="reopen"', detail_source)
        self.assertIn("Reopen", detail_source)
        self.assertIn('action="cancel"', detail_source)
        self.assertIn("Cancel", detail_source)
        self.assertNotIn("Field Path", detail_source)

    def test_shared_layout_context_counts_queries_needing_response(self):
        user = SimpleNamespace(pk=9, is_authenticated=True)
        request = SimpleNamespace(user=user)
        read_service = _ReadServiceRepositoryStub()

        with (
            patch(
                "apps.shared.context_processors.StudyDropdownHandler",
                return_value=_SharedDropdownHandler(selected_id=1),
            ),
            patch(
                "apps.shared.context_processors.SiteDropdownHandler",
                return_value=_SharedDropdownHandler(selected_id=2),
            ),
            patch(
                "apps.shared.context_processors.get_layout_nav_permissions",
                return_value={
                    "subjects": True,
                    "queries": True,
                    "sites": True,
                    "studies": False,
                    "users": False,
                    "dashboard": False,
                },
            ),
            patch(
                "apps.reconcile.application.ReconcileDataQueryReadService",
                return_value=ReconcileDataQueryReadService(repository=read_service),
            ),
        ):
            context = shared_select_options(request)

        self.assertEqual(context["layout_queries_need_response_count"], 4)
        self.assertEqual(
            read_service.assigned_count_for_study_site_kwargs,
            {
                "study_id": 1,
                "site_id": 2,
                "user_id": 9,
            },
        )

    def test_shared_layout_context_is_built_once_per_request(self):
        user = SimpleNamespace(pk=9, is_authenticated=True)
        first_request = SimpleNamespace(user=user)
        second_request = SimpleNamespace(user=user)

        with (
            patch(
                "apps.shared.context_processors.StudyDropdownHandler",
                return_value=_SharedDropdownHandler(selected_id=1),
            ) as study_dropdown_handler,
            patch(
                "apps.shared.context_processors.SiteDropdownHandler",
                return_value=_SharedDropdownHandler(selected_id=2),
            ) as site_dropdown_handler,
            patch(
                "apps.shared.context_processors.get_layout_nav_permissions",
                return_value={
                    "subjects": True,
                    "queries": False,
                    "sites": True,
                    "studies": False,
                    "users": False,
                    "dashboard": False,
                },
            ) as get_nav_permissions,
        ):
            first_context = shared_select_options(first_request)
            cached_context = shared_select_options(first_request)
            second_context = shared_select_options(second_request)

        self.assertIs(cached_context, first_context)
        self.assertIsNot(second_context, first_context)
        self.assertEqual(study_dropdown_handler.call_count, 2)
        self.assertEqual(site_dropdown_handler.call_count, 2)
        self.assertEqual(get_nav_permissions.call_count, 2)


class QueryLifecycleActionAPIViewTests(SimpleTestCase):
    def test_post_resolve_maps_to_reconcile_public_api(self):
        request = RequestFactory().post(
            "/api/studies/1/queries/2/resolve/",
            data='{"message_text": "Confirmed"}',
            content_type="application/json",
        )
        request.user = SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda permission: False)
        context = SimpleNamespace(study_id=1, site_id=9)

        with (
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.get_page_state_contexts",
                return_value={33: context},
            ),
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.user_can_access_permission",
                return_value=True,
            ) as can_access,
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.ReconcileDataQueryWriteService",
                return_value=_QueryActionServiceStub(
                    scope={
                        "dataquery_id": 2,
                        "page_state_id": 33,
                        "field_template_id": 44,
                        "status": "answered",
                    },
                    result={
                        "changed": True,
                        "status": "resolved",
                        "message_text": "Confirmed",
                        "message_type": "resolution",
                    },
                ),
            ) as service_class,
        ):
            response = QueryLifecycleActionAPIView().post(
                request,
                study_id=1,
                query_id=2,
                action="resolve",
            )

        self.assertEqual(response.status_code, 200)
        can_access.assert_called_once_with(
            request.user,
            "QUERY.CLOSE",
            study_id=1,
            site_id=9,
        )
        service = service_class.return_value
        self.assertEqual(
            service.resolve_kwargs,
            {
                "dataquery_id": 2,
                "page_state_id": 33,
                "field_template_id": 44,
                "message_text": "Confirmed",
                "actor_user_id": 7,
            },
        )

    def test_post_request_clarification_maps_to_open_transition(self):
        request = RequestFactory().post(
            "/api/studies/1/queries/2/request_clarification/",
            data='{"message_text": "Please clarify"}',
            content_type="application/json",
        )
        request.user = SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda permission: False)
        context = SimpleNamespace(study_id=1, site_id=9)

        with (
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.get_page_state_contexts",
                return_value={33: context},
            ),
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.user_can_access_permission",
                return_value=True,
            ) as can_access,
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.ReconcileDataQueryWriteService",
                return_value=_QueryActionServiceStub(
                    scope={
                        "dataquery_id": 2,
                        "page_state_id": 33,
                        "field_template_id": 44,
                        "status": "answered",
                    },
                    result={
                        "changed": True,
                        "status": "open",
                        "message_text": "Please clarify",
                        "message_type": "status_change",
                    },
                ),
            ) as service_class,
        ):
            response = QueryLifecycleActionAPIView().post(
                request,
                study_id=1,
                query_id=2,
                action="request_clarification",
            )

        self.assertEqual(response.status_code, 200)
        can_access.assert_called_once_with(
            request.user,
            "QUERY.RETURN",
            study_id=1,
            site_id=9,
        )
        service = service_class.return_value
        self.assertEqual(
            service.clarification_kwargs,
            {
                "dataquery_id": 2,
                "page_state_id": 33,
                "field_template_id": 44,
                "message_text": "Please clarify",
                "actor_user_id": 7,
            },
        )

    def test_post_reopen_maps_to_open_transition(self):
        request = RequestFactory().post(
            "/api/studies/1/queries/2/reopen/",
            data='{"message_text": "Issue found during review"}',
            content_type="application/json",
        )
        request.user = SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda permission: False)
        context = SimpleNamespace(study_id=1, site_id=9)

        with (
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.get_page_state_contexts",
                return_value={33: context},
            ),
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.user_can_access_permission",
                return_value=True,
            ) as can_access,
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.ReconcileDataQueryWriteService",
                return_value=_QueryActionServiceStub(
                    scope={
                        "dataquery_id": 2,
                        "page_state_id": 33,
                        "field_template_id": 44,
                        "status": "resolved",
                    },
                    result={
                        "changed": True,
                        "status": "open",
                        "message_text": "Issue found during review",
                        "message_type": "status_change",
                    },
                ),
            ) as service_class,
        ):
            response = QueryLifecycleActionAPIView().post(
                request,
                study_id=1,
                query_id=2,
                action="reopen",
            )

        self.assertEqual(response.status_code, 200)
        can_access.assert_called_once_with(
            request.user,
            "QUERY.REOPEN",
            study_id=1,
            site_id=9,
        )
        service = service_class.return_value
        self.assertEqual(
            service.reopen_kwargs,
            {
                "dataquery_id": 2,
                "page_state_id": 33,
                "field_template_id": 44,
                "message_text": "Issue found during review",
                "actor_user_id": 7,
            },
        )

    def test_post_cancel_maps_to_cancel_transition(self):
        request = RequestFactory().post(
            "/api/studies/1/queries/2/cancel/",
            data='{"message_text": "Opened by mistake"}',
            content_type="application/json",
        )
        request.user = SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda permission: False)
        context = SimpleNamespace(study_id=1, site_id=9)

        with (
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.get_page_state_contexts",
                return_value={33: context},
            ),
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.user_can_access_permission",
                return_value=True,
            ) as can_access,
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.ReconcileDataQueryWriteService",
                return_value=_QueryActionServiceStub(
                    scope={
                        "dataquery_id": 2,
                        "page_state_id": 33,
                        "field_template_id": 44,
                        "status": "open",
                    },
                    result={
                        "changed": True,
                        "status": "cancelled",
                        "message_text": "Opened by mistake",
                        "message_type": "status_change",
                    },
                ),
            ) as service_class,
        ):
            response = QueryLifecycleActionAPIView().post(
                request,
                study_id=1,
                query_id=2,
                action="cancel",
            )

        self.assertEqual(response.status_code, 200)
        can_access.assert_called_once_with(
            request.user,
            "QUERY.CANCEL",
            study_id=1,
            site_id=9,
        )
        service = service_class.return_value
        self.assertEqual(
            service.cancel_kwargs,
            {
                "dataquery_id": 2,
                "page_state_id": 33,
                "field_template_id": 44,
                "message_text": "Opened by mistake",
                "actor_user_id": 7,
            },
        )

    def test_post_rejects_action_for_wrong_status(self):
        request = RequestFactory().post(
            "/api/studies/1/queries/2/close/",
            data="{}",
            content_type="application/json",
        )
        request.user = SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda permission: False)

        with (
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.get_page_state_contexts",
                return_value={33: SimpleNamespace(study_id=1, site_id=9)},
            ),
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.user_can_access_permission",
                return_value=True,
            ),
            patch(
                "apps.reconcile.presentation.api.views.query_lifecycle.ReconcileDataQueryWriteService",
                return_value=_QueryActionServiceStub(
                    scope={
                        "dataquery_id": 2,
                        "page_state_id": 33,
                        "field_template_id": 44,
                        "status": "open",
                    },
                    result={},
                ),
            ),
        ):
            response = QueryLifecycleActionAPIView().post(
                request,
                study_id=1,
                query_id=2,
                action="close",
            )

        self.assertEqual(response.status_code, 400)


class ValidationIssueLifecycleActionAPIViewTests(SimpleTestCase):
    def test_post_reopen_requires_validation_issue_reopen_permission(self):
        request = RequestFactory().post(
            "/api/studies/1/validation-issues/7/reopen/",
            data='{"message_text": "Please answer again."}',
            content_type="application/json",
        )
        request.user = SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda permission: False)
        context = SimpleNamespace(study_id=1, site_id=9)
        service = _ValidationIssueActionServiceStub(
            scope={
                "issue_id": 7,
                "page_state_id": 33,
                "status": "ACKNOWLEDGED",
            }
        )

        with (
            patch(
                "apps.reconcile.presentation.api.views.validation_issue_lifecycle.get_page_state_contexts",
                return_value={33: context},
            ),
            patch(
                "apps.reconcile.presentation.api.views.validation_issue_lifecycle.user_can_access_permission",
                return_value=True,
            ) as can_access,
            patch(
                "apps.reconcile.presentation.api.views.validation_issue_lifecycle.ReconcileDataQueryWriteService",
                return_value=service,
            ),
        ):
            response = ValidationIssueLifecycleActionAPIView().post(
                request,
                study_id=1,
                issue_id=7,
                action="reopen",
            )

        self.assertEqual(response.status_code, 200)
        can_access.assert_called_once_with(
            request.user,
            "VALIDATION_ISSUE.REOPEN",
            study_id=1,
            site_id=9,
        )
        self.assertEqual(
            service.reopen_kwargs,
            {
                "issue_id": 7,
                "reason": "Please answer again.",
                "actor_user_id": 7,
            },
        )

    def test_post_rejects_reopen_for_non_acknowledged_issue(self):
        request = RequestFactory().post(
            "/api/studies/1/validation-issues/7/reopen/",
            data='{"message_text": "Please answer again."}',
            content_type="application/json",
        )
        request.user = SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda permission: False)
        service = _ValidationIssueActionServiceStub(
            scope={
                "issue_id": 7,
                "page_state_id": 33,
                "status": "ACKNOWLEDGEMENT_REQUIRED",
            }
        )

        with (
            patch(
                "apps.reconcile.presentation.api.views.validation_issue_lifecycle.get_page_state_contexts",
                return_value={33: SimpleNamespace(study_id=1, site_id=9)},
            ),
            patch(
                "apps.reconcile.presentation.api.views.validation_issue_lifecycle.user_can_access_permission",
                return_value=True,
            ),
            patch(
                "apps.reconcile.presentation.api.views.validation_issue_lifecycle.ReconcileDataQueryWriteService",
                return_value=service,
            ),
        ):
            response = ValidationIssueLifecycleActionAPIView().post(
                request,
                study_id=1,
                issue_id=7,
                action="reopen",
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(hasattr(service, "reopen_kwargs"))


class _QueryActionServiceStub:
    def __init__(self, *, scope, result):
        self.scope = scope
        self.result = result

    def query_action_scope(self, *, dataquery_id):
        self.scope_query_id = dataquery_id
        return self.scope

    def resolve_query(self, **kwargs):
        self.resolve_kwargs = kwargs
        return self.result

    def reply_to_query(self, **kwargs):
        self.answer_kwargs = kwargs
        return self.result

    def close_resolved_query(self, **kwargs):
        self.close_kwargs = kwargs
        return self.result

    def reopen_query(self, **kwargs):
        self.reopen_kwargs = kwargs
        return self.result

    def request_clarification(self, **kwargs):
        self.clarification_kwargs = kwargs
        return self.result

    def cancel_dataquery(self, **kwargs):
        self.cancel_kwargs = kwargs
        return self.result


class _ValidationIssueActionServiceStub:
    def __init__(self, *, scope):
        self.scope = scope

    def validation_issue_action_scope(self, *, issue_id):
        self.scope_issue_id = issue_id
        return self.scope

    def reopen_validation_issue(self, **kwargs):
        self.reopen_kwargs = kwargs
        return {
            "issue_id": kwargs["issue_id"],
            "status": "ACKNOWLEDGEMENT_REQUIRED",
            "changed": True,
        }


class _DummyWorkbenchReader:
    def __init__(self):
        self.last_read_kwargs = None

    def read(self, **kwargs):
        self.last_read_kwargs = kwargs
        return _DummyWorkbenchReaderResult()


class _DummyWorkbenchReaderResult:
    def __init__(self):
        self.items = []
        self.validation_issues = []
        self.summary = SimpleNamespace(
            total=0,
            open=0,
            awaiting_site_response=0,
            awaiting_review=0,
            blocking_open=0,
            resolved=0,
            closed=0,
            validation_issues_open=0,
            hard_validation_issues_open=0,
        )


class _WorkbenchSiteDropdownHandler:
    def __init__(self, request=None, study_id=None, **kwargs):
        self.request = request
        self.study_id = study_id

    def build(self):
        return SimpleNamespace(selected_id=1)


class _SharedDropdownHandler:
    def __init__(self, selected_id):
        self.selected_id = selected_id

    def build(self):
        return SimpleNamespace(
            selected_id=self.selected_id,
            select_display_text="Selected",
            select_options=[],
        )


class _ReadServiceRepositoryStub:
    def __init__(self):
        self.assigned_count_kwargs = None
        self.assigned_count_for_study_site_kwargs = None

    def count_open_queries_assigned_to_user(self, **kwargs):
        self.assigned_count_kwargs = kwargs
        return 4

    def count_open_queries_assigned_to_user_for_study_site(self, **kwargs):
        self.assigned_count_for_study_site_kwargs = kwargs
        return 4


class _DataQueryManagerStub:
    def __init__(self, *, count):
        self.count = count
        self.filter_kwargs = None
        self.filter_calls = []

    def filter(self, **kwargs):
        self.filter_kwargs = kwargs
        self.filter_calls.append(kwargs)
        return _CountQuerySet(self.count, self.filter_calls)


class _CountQuerySet:
    def __init__(self, count, filter_calls=None):
        self._count = count
        self.filter_calls = filter_calls if filter_calls is not None else []

    def filter(self, **kwargs):
        self.filter_calls.append(kwargs)
        return self

    def count(self):
        return self._count


class _WorkbenchRepository:
    def __init__(self, rows=None, threads=None):
        self.rows = rows or []
        self.threads = threads or []
        self.last_query_kwargs = None
        self.last_validation_issue_kwargs = None

    def summarize_workbench(self, *, page_state_ids):
        return {
            "total": 4,
            "open": 1,
            "awaiting_site_response": 2,
            "awaiting_review": 1,
            "blocking_open": 1,
            "resolved": 1,
            "closed": 0,
            "validation_issues_open": 1,
            "hard_validation_issues_open": 1,
            "actionable_for_current_user": 3,
        }

    def list_workbench_queries(self, **kwargs):
        self.last_query_kwargs = kwargs
        if kwargs["bucket"] == "validation_issues":
            return []
        return self.rows

    def get_workbench_query_detail(self, *, query_id, can_view_internal_thread):
        for row in self.rows:
            if row["query_id"] == query_id:
                return {**row, "threads": self.threads}
        return None

    def list_workbench_validation_issues(self, **kwargs):
        self.last_validation_issue_kwargs = kwargs
        return [
            {
                "issue_id": 7,
                "page_state_id": 10,
                "status": "ACKNOWLEDGED",
                "severity": "major",
                "message": "Required value is missing",
                "failed_value": None,
                "created_at": None,
                "resolved_at": None,
                "acknowledged_by_id": 8,
                "acknowledged_at": None,
                "field_label": "Reticulocyte % (RET%)",
            }
        ]


class _ThreadQuerySet:
    def __init__(self, rows):
        self.rows = rows
        self.ordered_by = None
        self.excluded_with = None

    def order_by(self, *fields):
        self.ordered_by = fields
        return self

    def values(self, *fields):
        self.selected_fields = fields
        return self.rows

    def exclude(self, **kwargs):
        self.excluded_with = kwargs
        return self


def _query_row():
    return {
        "query_id": 11,
        "page_state_id": 10,
        "status": "answered",
        "source": "manual",
        "query_type": "manual",
        "severity": "major",
        "is_blocking": True,
        "question_text": "Please confirm the weight value",
        "resolution_note": "",
        "field_path": "$.weight",
        "value_snapshot": "72",
        "opened_at": None,
        "answered_at": None,
        "resolved_at": None,
        "closed_at": None,
        "last_activity_at": None,
        "reply_count": 3,
        "assigned_to_id": 8,
        "opened_by_id": 9,
        "field_label": "Weight",
    }
