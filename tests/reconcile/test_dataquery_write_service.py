from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.reconcile.application import ReconcileDataQueryWriteService
from apps.reconcile.infrastructure.repositories.dataquery_write import DjangoReconcileDataQueryWriteRepository
from apps.reconcile.models import (
    ReconcileDataQueryStatusChoices,
    ReconcileQueryThreadSourceChoices,
    ReconcileValidationIssueSnapshotResultChoices,
    ReconcileValidationIssueStatusChoices,
    ReconcileValidationRunSourceChoices,
)


class ReconcileDataQueryWriteServiceTests(SimpleTestCase):
    def test_add_update_value_threads_for_changed_fields_creates_system_thread_for_open_queries(self):
        repository = _ReconcileRepositoryStub()

        created_count = ReconcileDataQueryWriteService(repository=repository).add_update_value_threads_for_changed_fields(
            page_state_id=11,
            crf_template_id=31,
            values_by_field_key={
                "field_1": "Y",
                "field_2": "A,B",
                "field_3": "raw value",
                "missing": "ignored",
            },
            actor_user_id=99,
        )
        self.assertEqual(created_count, 3)
        self.assertEqual(
            [
                {
                    "dataquery_id": call["dataquery_id"],
                    "page_state_id": call["page_state_id"],
                    "field_template_id": call["field_template_id"],
                    "actor_user_id": call["actor_user_id"],
                }
                for call in repository.answered_calls
            ],
            [
                {"dataquery_id": 101, "page_state_id": 11, "field_template_id": 1, "actor_user_id": 99},
                {"dataquery_id": 102, "page_state_id": 11, "field_template_id": 2, "actor_user_id": 99},
                {"dataquery_id": 103, "page_state_id": 11, "field_template_id": 3, "actor_user_id": 99},
            ],
        )
        self.assertEqual(
            repository.created_threads,
            [
                {
                    "dataquery_id": 101,
                    "message_text": "Update value to **Yes**",
                    "message_type": "comment",
                    "actor_user_id": 99,
                    "source": ReconcileQueryThreadSourceChoices.SYSTEM,
                },
                {
                    "dataquery_id": 102,
                    "message_text": "Update value to **Alpha, Beta**",
                    "message_type": "comment",
                    "actor_user_id": 99,
                    "source": ReconcileQueryThreadSourceChoices.SYSTEM,
                },
                {
                    "dataquery_id": 103,
                    "message_text": "Update value to **raw value**",
                    "message_type": "comment",
                    "actor_user_id": 99,
                    "source": ReconcileQueryThreadSourceChoices.SYSTEM,
                },
            ],
        )

    def test_reply_to_query_marks_query_answered_by_reply_actor(self):
        repository = _ReplyRepositoryStub()

        result = ReconcileDataQueryWriteService(repository=repository).reply_to_query(
            dataquery_id=101,
            page_state_id=23,
            field_template_id=11,
            message_text="Answered by site",
            actor_user_id=7,
        )

        self.assertEqual(result["dataquery_id"], 101)
        self.assertEqual(repository.answered_calls[0]["dataquery_id"], 101)
        self.assertEqual(repository.answered_calls[0]["page_state_id"], 23)
        self.assertEqual(repository.answered_calls[0]["field_template_id"], 11)
        self.assertEqual(repository.answered_calls[0]["actor_user_id"], 7)
        self.assertIs(repository.answered_calls[0]["now"], repository.created_threads[0]["now"])
        self.assertEqual(result["status"], "answered")
        self.assertIs(result["changed"], True)

    def test_reply_to_query_does_not_create_thread_when_status_update_fails(self):
        repository = _ReplyRepositoryStub(can_answer=False)

        result = ReconcileDataQueryWriteService(repository=repository).reply_to_query(
            dataquery_id=101,
            page_state_id=23,
            field_template_id=11,
            message_text="Answered by site",
            actor_user_id=7,
        )

        self.assertIs(result["changed"], False)
        self.assertEqual(repository.created_threads, [])
        self.assertEqual(repository.answered_calls[0]["dataquery_id"], 101)

    def test_resolve_query_marks_query_resolved(self):
        repository = _ReplyRepositoryStub()

        result = ReconcileDataQueryWriteService(repository=repository).resolve_query(
            dataquery_id=101,
            page_state_id=23,
            field_template_id=11,
            message_text="Resolved by CRA",
            actor_user_id=7,
        )

        self.assertEqual(result["status"], "resolved")
        self.assertEqual(repository.resolved_calls[0]["resolution_note"], "Resolved by CRA")
        self.assertIs(repository.resolved_calls[0]["now"], repository.created_threads[0]["now"])

    def test_close_resolved_query_marks_query_closed(self):
        repository = _ReplyRepositoryStub()

        result = ReconcileDataQueryWriteService(repository=repository).close_resolved_query(
            dataquery_id=101,
            page_state_id=23,
            field_template_id=11,
            message_text="",
            actor_user_id=7,
        )

        self.assertEqual(result["status"], "closed")
        self.assertEqual(repository.closed_resolved_calls[0]["actor_user_id"], 7)

    def test_reopen_query_marks_query_open(self):
        repository = _ReplyRepositoryStub()

        result = ReconcileDataQueryWriteService(repository=repository).reopen_query(
            dataquery_id=101,
            page_state_id=23,
            field_template_id=11,
            message_text="Needs more evidence",
            actor_user_id=7,
        )

        self.assertEqual(result["status"], "open")
        self.assertEqual(repository.reopen_calls[0]["actor_user_id"], 7)

    def test_request_clarification_marks_answered_query_open(self):
        repository = _ReplyRepositoryStub()

        result = ReconcileDataQueryWriteService(repository=repository).request_clarification(
            dataquery_id=101,
            page_state_id=23,
            field_template_id=11,
            message_text="Please clarify the updated value",
            actor_user_id=7,
        )

        self.assertEqual(result["status"], "open")
        self.assertIs(result["changed"], True)
        self.assertEqual(repository.clarification_calls[0]["dataquery_id"], 101)
        self.assertIs(repository.clarification_calls[0]["now"], repository.created_threads[0]["now"])
        self.assertEqual(repository.created_threads[0]["message_type"], "status_change")
        self.assertEqual(repository.created_threads[0]["message_text"], "Please clarify the updated value")

    def test_reply_to_query_allows_non_participant(self):
        repository = _ReplyRepositoryStub(can_respond=False)

        result = ReconcileDataQueryWriteService(repository=repository).reply_to_query(
            dataquery_id=101,
            page_state_id=23,
            field_template_id=11,
            message_text="Answered by site",
            actor_user_id=99,
        )

        self.assertEqual(result["dataquery_id"], 101)
        self.assertEqual(repository.created_threads[0]["actor_user_id"], 99)
        self.assertEqual(repository.answered_calls[0]["actor_user_id"], 99)
        self.assertFalse(hasattr(repository, "response_actor_check"))

    def test_cancel_query_marks_query_cancelled(self):
        repository = _ReplyRepositoryStub()

        result = ReconcileDataQueryWriteService(repository=repository).cancel_query(
            dataquery_id=101,
            page_state_id=23,
            field_template_id=11,
            actor_user_id=7,
        )

        self.assertIs(result["cancelled"], True)
        self.assertEqual(repository.cancelled_calls[0]["dataquery_id"], 101)
        self.assertEqual(repository.cancelled_calls[0]["page_state_id"], 23)
        self.assertEqual(repository.cancelled_calls[0]["field_template_id"], 11)
        self.assertEqual(repository.cancelled_calls[0]["actor_user_id"], 7)

    def test_cancel_dataquery_marks_query_cancelled_with_status_thread(self):
        repository = _ReplyRepositoryStub()

        result = ReconcileDataQueryWriteService(repository=repository).cancel_dataquery(
            dataquery_id=101,
            page_state_id=23,
            field_template_id=11,
            message_text="Opened by mistake",
            actor_user_id=7,
        )

        self.assertEqual(result["status"], "cancelled")
        self.assertIs(result["changed"], True)
        self.assertEqual(repository.cancelled_calls[0]["dataquery_id"], 101)
        self.assertIs(repository.cancelled_calls[0]["now"], repository.created_threads[0]["now"])
        self.assertEqual(repository.created_threads[0]["message_type"], "status_change")
        self.assertEqual(repository.created_threads[0]["message_text"], "Opened by mistake")

    def test_create_validation_failure_records_creates_soft_issue_and_query(self):
        repository = _ReconcileRepositoryStub()

        result = ReconcileDataQueryWriteService(repository=repository).create_validation_failure_records(
            page_state_id=11,
            failures=[
                {
                    "rule_id": 201,
                    "field_template_id": 1,
                    "field_key": "field_1",
                    "mode": "SOFT",
                    "severity": "warning",
                    "message": "Please acknowledge.",
                    "failed_value": "",
                },
                {
                    "rule_id": 202,
                    "field_template_id": 2,
                    "field_key": "field_2",
                    "mode": "QUERY",
                    "severity": "error",
                    "message": "Please resolve query.",
                    "failed_value": "bad",
                },
                {
                    "rule_id": 203,
                    "field_template_id": 3,
                    "field_key": "field_3",
                    "mode": "HARD",
                    "severity": "error",
                    "message": "Hard rule failed.",
                    "failed_value": "blocked",
                },
            ],
            actor_user_id=99,
        )

        self.assertEqual(result, {"soft_issue_count": 2, "query_count": 1})
        self.assertEqual(repository.created_validation_runs[0]["page_state_id"], 11)
        self.assertEqual(
            repository.created_validation_runs[0]["source"],
            ReconcileValidationRunSourceChoices.SUBMIT_FOR_REVIEW,
        )
        self.assertEqual(repository.created_soft_issues[0]["validation_run_id"], 8801)
        self.assertEqual(repository.created_soft_issues[0]["items"][0]["rule_id"], 201)
        self.assertEqual(repository.created_soft_issues[0]["items"][1]["rule_id"], 203)
        self.assertEqual(repository.created_soft_issues[0]["items"][1]["mode"], "HARD")
        self.assertEqual(repository.created_validation_queries[0]["validation_rule_id"], 202)
        self.assertEqual(repository.created_validation_queries[0]["severity"], "major")
        self.assertEqual(repository.created_threads[-1]["message_text"], "Please resolve query.")

    def test_acknowledge_validation_issues_requires_comment(self):
        repository = _ReconcileRepositoryStub()

        with self.assertRaisesMessage(ValueError, "Acknowledgement comment is required."):
            ReconcileDataQueryWriteService(repository=repository).acknowledge_validation_issues(
                page_state_id=11,
                issues=[{"issue_id": 701, "comment": ""}],
                actor_user_id=99,
            )

        self.assertEqual(repository.acknowledged_validation_issues, [])

    def test_acknowledge_validation_issues_delegates_normalized_items(self):
        repository = _ReconcileRepositoryStub()

        result = ReconcileDataQueryWriteService(repository=repository).acknowledge_validation_issues(
            page_state_id=11,
            issues=[{"issue_id": "701", "comment": "Reviewed warning."}],
            actor_user_id=99,
        )

        self.assertEqual(result, {"acknowledged_issue_ids": [701], "acknowledged_count": 1})
        self.assertEqual(repository.created_validation_runs[0]["page_state_id"], 11)
        self.assertEqual(
            repository.created_validation_runs[0]["source"],
            ReconcileValidationRunSourceChoices.VALIDATION_ISSUE_ACKNOWLEDGEMENT,
        )
        self.assertEqual(repository.acknowledged_validation_issues[0]["page_state_id"], 11)
        self.assertEqual(repository.acknowledged_validation_issues[0]["validation_run_id"], 8801)
        self.assertEqual(repository.acknowledged_validation_issues[0]["items"], [{"issue_id": 701, "comment": "Reviewed warning."}])

    def test_reopen_validation_issue_requires_reason(self):
        repository = _ReconcileRepositoryStub()

        with self.assertRaisesMessage(ValueError, "Reopen reason is required."):
            ReconcileDataQueryWriteService(repository=repository).reopen_validation_issue(
                issue_id=701,
                reason=" ",
                actor_user_id=99,
            )

        self.assertEqual(repository.reopened_validation_issues, [])

    def test_reopen_validation_issue_uses_issue_scope(self):
        repository = _ReconcileRepositoryStub()

        result = ReconcileDataQueryWriteService(repository=repository).reopen_validation_issue(
            issue_id=701,
            reason="Please provide another response.",
            actor_user_id=99,
        )

        self.assertEqual(
            result,
            {
                "issue_id": 701,
                "page_state_id": 11,
                "status": ReconcileValidationIssueStatusChoices.ACKNOWLEDGEMENT_REQUIRED,
                "changed": True,
            },
        )
        self.assertEqual(repository.validation_issue_scope_calls, [{"issue_id": 701}])
        self.assertEqual(repository.reopened_validation_issues[0]["page_state_id"], 11)
        self.assertEqual(
            repository.reopened_validation_issues[0]["reason"],
            "Please provide another response.",
        )

    def test_correct_resolved_validation_issues_marks_changed_valid_fields_corrected(self):
        repository = _ReconcileRepositoryStub()

        result = ReconcileDataQueryWriteService(repository=repository).correct_resolved_validation_issues(
            page_state_id=11,
            crf_template_id=31,
            changed_field_keys=["field_1"],
            values_by_field_key={"field_1": "19"},
            failures=[],
            actor_user_id=99,
        )

        self.assertEqual(result, {"corrected_issue_ids": [701], "corrected_count": 1})
        self.assertEqual(repository.corrected_validation_issues[0]["issue_id"], 701)
        self.assertEqual(
            repository.corrected_validation_issues[0]["correction_comment"],
            "Cập nhật dữ liệu từ 8 thành 19",
        )


class ReconcileDataQueryWriteRepositoryTests(SimpleTestCase):
    def test_create_manual_open_query_persists_current_page_entry_field_context(self):
        repository = _ReconcileRepositoryWithEntryContext()

        with patch(
            "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileDataQuery.objects.create",
            return_value=SimpleNamespace(pk=501),
        ) as create_dataquery:
            dataquery = repository.create_manual_open_query(
                page_state_id=23,
                field_template_id=11,
                question_text="Please review",
                actor_user_id=7,
                now="now",
            )

        self.assertEqual(dataquery.pk, 501)
        created = create_dataquery.call_args.kwargs
        self.assertEqual(created["page_entry_id"], 301)
        self.assertEqual(created["field_template_id"], 11)
        self.assertEqual(created["value_snapshot"], "1")
        self.assertEqual(created["field_path"], "$.CONTRACEPT_YN")
        self.assertEqual(created["data_version"], "v2")
        self.assertEqual(created["assigned_to_id"], 42)

    def test_entry_field_value_snapshot_uses_field_id_fallback_and_jsonpath_bracket_notation(self):
        snapshot, storage_key = DjangoReconcileDataQueryWriteRepository._entry_field_value_snapshot(
            payload={"field_12": ["A", "B"]},
            field_key="field key with space",
            field_template_id=12,
        )

        self.assertEqual(snapshot, '["A", "B"]')
        self.assertEqual(storage_key, "field_12")
        self.assertEqual(
            DjangoReconcileDataQueryWriteRepository._jsonpath_for_field_key("field key with space"),
            '$["field key with space"]',
        )

    def test_entry_field_value_snapshot_uses_field_key_for_jsonpath_evaluator(self):
        snapshot, storage_key = DjangoReconcileDataQueryWriteRepository._entry_field_value_snapshot(
            payload={"CONTRACEPT_YN": "1", "PREGPLAN_YN": "0"},
            field_key="CONTRACEPT_YN",
            field_template_id=12,
        )

        self.assertEqual(snapshot, "1")
        self.assertEqual(storage_key, "CONTRACEPT_YN")
        self.assertEqual(
            DjangoReconcileDataQueryWriteRepository._jsonpath_for_field_key(storage_key),
            "$.CONTRACEPT_YN",
        )

    def test_canonical_field_path_uses_repeat_row_context(self):
        self.assertEqual(
            DjangoReconcileDataQueryWriteRepository._canonical_field_path(
                section_code="MEDS",
                storage_key="MED_NAME",
                is_repeatable=True,
            ),
            "groups.MEDS.rows[row_001].items.MED_NAME",
        )
        self.assertEqual(
            DjangoReconcileDataQueryWriteRepository._canonical_field_path(
                section_code="MEDS",
                storage_key="MED_NAME__repeat_2",
                is_repeatable=True,
            ),
            "groups.MEDS.rows[row_002].items.MED_NAME",
        )
        self.assertEqual(
            DjangoReconcileDataQueryWriteRepository._field_path_candidates(
                section_code="MEDS",
                storage_key="MED_NAME",
                is_repeatable=True,
                field_path="groups.MEDS.rows[row_001].items.MED_NAME",
            ),
            (
                "groups.MEDS.rows[row_001].items.MED_NAME",
                "groups.MEDS.items.MED_NAME",
            ),
        )

    def test_soft_validation_issue_reuses_existing_issue_and_appends_fail_snapshot(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        existing_issue = SimpleNamespace(
            pk=701,
            mode="SOFT",
            severity="warning",
            status=ReconcileValidationIssueStatusChoices.CORRECTED,
            message="Old warning",
            failed_value="old",
            field_instance_id=301,
            resolved_at="earlier",
            save=lambda **kwargs: None,
        )

        with (
            patch.object(DjangoReconcileDataQueryWriteRepository, "get_current_field_entry_id", return_value=301),
            patch.object(
                DjangoReconcileDataQueryWriteRepository,
                "_list_reusable_validation_issues_by_signature",
                return_value={
                    DjangoReconcileDataQueryWriteRepository._validation_issue_signature(
                        rule_id=801,
                        field_template_id=11,
                        field_instance_id=None,
                    ): existing_issue
                },
            ),
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssueSnapshot.objects.create",
            ) as create_snapshot,
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssue.objects.create",
            ) as create_issue,
        ):
            created_count = repository.bulk_create_soft_validation_issues(
                page_state_id=23,
                items=[
                    {
                        "rule_id": 801,
                        "field_template_id": 11,
                        "message": "Needs ACK",
                        "severity": "warning",
                        "failed_value": "new",
                    }
                ],
                actor_user_id=7,
                now="now",
                validation_run_id=8801,
                evaluated_values_by_field_template_id={11: "new"},
                data_version=9,
            )

        self.assertEqual(created_count, 1)
        create_issue.assert_not_called()
        self.assertEqual(existing_issue.status, ReconcileValidationIssueStatusChoices.ACKNOWLEDGEMENT_REQUIRED)
        self.assertEqual(existing_issue.failed_value, "new")
        self.assertIsNone(existing_issue.resolved_at)
        create_snapshot.assert_called_once_with(
            validation_issue_id=701,
            validation_run_id=8801,
            result="FAIL",
            evaluated_values_json="new",
            message="Needs ACK",
            severity="warning",
            data_version=9,
            created_at="now",
            related_audit_event_id=None,
        )

    def test_soft_validation_issue_creates_new_issue_and_marks_missing_failure_as_pass_snapshot(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        passing_issue = SimpleNamespace(
            pk=702,
            mode="SOFT",
            severity="minor",
            status=ReconcileValidationIssueStatusChoices.ACKNOWLEDGEMENT_REQUIRED,
            message="Old warning",
            failed_value="old",
            field_instance_id=None,
            rule=SimpleNamespace(field_template_id=12),
            resolved_at=None,
            save=lambda **kwargs: None,
        )

        with (
            patch.object(DjangoReconcileDataQueryWriteRepository, "get_current_field_entry_id", return_value=301),
            patch.object(
                DjangoReconcileDataQueryWriteRepository,
                "_list_reusable_validation_issues_by_signature",
                return_value={
                    DjangoReconcileDataQueryWriteRepository._validation_issue_signature(
                        rule_id=999,
                        field_template_id=12,
                        field_instance_id=None,
                    ): passing_issue
                },
            ),
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssueSnapshot.objects.create",
            ) as create_snapshot,
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssue.objects.create",
                return_value=SimpleNamespace(pk=701),
            ) as create_issue,
        ):
            created_count = repository.bulk_create_soft_validation_issues(
                page_state_id=23,
                items=[
                    {
                        "rule_id": 801,
                        "field_template_id": 11,
                        "message": "Needs ACK",
                        "severity": "major",
                        "failed_value": "new",
                    }
                ],
                actor_user_id=7,
                now="now",
                validation_run_id=8801,
                evaluated_values_by_field_template_id={11: "new"},
                data_version=9,
            )

        self.assertEqual(created_count, 1)
        create_issue.assert_called_once()
        self.assertEqual(passing_issue.status, ReconcileValidationIssueStatusChoices.CORRECTED)
        self.assertEqual(passing_issue.resolved_at, "now")
        self.assertEqual(create_snapshot.call_count, 2)

    def test_soft_validation_issue_defaults_missing_snapshot_values_to_empty_object(self):
        repository = DjangoReconcileDataQueryWriteRepository()

        with (
            patch.object(DjangoReconcileDataQueryWriteRepository, "get_current_field_entry_id", return_value=301),
            patch.object(
                DjangoReconcileDataQueryWriteRepository,
                "_list_reusable_validation_issues_by_signature",
                return_value={},
            ),
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssueSnapshot.objects.create",
            ) as create_snapshot,
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssue.objects.create",
                return_value=SimpleNamespace(pk=701),
            ),
        ):
            created_count = repository.bulk_create_soft_validation_issues(
                page_state_id=23,
                items=[
                    {
                        "rule_id": 801,
                        "field_template_id": 11,
                        "message": "Needs ACK",
                        "severity": "major",
                        "failed_value": "new",
                    }
                ],
                actor_user_id=7,
                now="now",
                validation_run_id=8801,
                evaluated_values_by_field_template_id={},
                data_version=9,
            )

        self.assertEqual(created_count, 1)
        create_snapshot.assert_called_once_with(
            validation_issue_id=701,
            validation_run_id=8801,
            result="FAIL",
            evaluated_values_json={},
            message="Needs ACK",
            severity="major",
            data_version=9,
            created_at="now",
            related_audit_event_id=None,
        )

    def test_soft_validation_issue_does_not_append_pass_snapshot_for_already_corrected_issue(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        corrected_issue = SimpleNamespace(
            pk=702,
            mode="SOFT",
            severity="minor",
            status=ReconcileValidationIssueStatusChoices.CORRECTED,
            message="Old warning",
            failed_value="old",
            field_instance_id=None,
            rule=SimpleNamespace(field_template_id=12),
            resolved_at="earlier",
            save=lambda **kwargs: None,
        )

        with (
            patch.object(DjangoReconcileDataQueryWriteRepository, "get_current_field_entry_id", return_value=301),
            patch.object(
                DjangoReconcileDataQueryWriteRepository,
                "_list_reusable_validation_issues_by_signature",
                return_value={
                    DjangoReconcileDataQueryWriteRepository._validation_issue_signature(
                        rule_id=999,
                        field_template_id=12,
                        field_instance_id=None,
                    ): corrected_issue
                },
            ),
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssueSnapshot.objects.create",
            ) as create_snapshot,
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssue.objects.create",
                return_value=SimpleNamespace(pk=701),
            ),
        ):
            created_count = repository.bulk_create_soft_validation_issues(
                page_state_id=23,
                items=[
                    {
                        "rule_id": 801,
                        "field_template_id": 11,
                        "message": "Needs ACK",
                        "severity": "major",
                        "failed_value": "new",
                    }
                ],
                actor_user_id=7,
                now="now",
                validation_run_id=8801,
                evaluated_values_by_field_template_id={11: "new"},
                data_version=9,
            )

        self.assertEqual(created_count, 1)
        create_snapshot.assert_called_once()

    def test_mark_query_answered_sets_answered_at_and_answered_by_id(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        query = _UpdateQuery()
        with patch(
            "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileDataQuery.objects.filter",
            return_value=query,
        ) as filter_query:
            answered = repository.mark_query_answered(
                dataquery_id=101,
                page_state_id=23,
                field_template_id=11,
                actor_user_id=7,
                now="now",
            )

        self.assertIs(answered, True)
        filter_query.assert_called_once_with(
            pk=101,
            page_state_id=23,
            field_template_id=11,
            deleted=False,
            status__in=(
                ReconcileDataQueryStatusChoices.OPEN,
                ReconcileDataQueryStatusChoices.ANSWERED,
            ),
        )
        self.assertEqual(query.updated_with["status"], "answered")
        self.assertEqual(query.updated_with["answered_at"], "now")
        self.assertEqual(query.updated_with["answered_by_id"], 7)
        self.assertEqual(query.updated_with["updated_at"], "now")
        self.assertEqual(query.updated_with["updated_by_id"], 7)

    def test_resolve_query_only_updates_answered_queries(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        query = _UpdateQuery()
        with patch(
            "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileDataQuery.objects.filter",
            return_value=query,
        ) as filter_query:
            resolved = repository.resolve_query(
                dataquery_id=101,
                page_state_id=23,
                field_template_id=11,
                resolution_note="Resolved",
                actor_user_id=7,
                now="now",
            )

        self.assertIs(resolved, True)
        filter_query.assert_called_once_with(
            pk=101,
            page_state_id=23,
            field_template_id=11,
            deleted=False,
            status=ReconcileDataQueryStatusChoices.ANSWERED,
        )
        self.assertEqual(query.updated_with["status"], "resolved")
        self.assertEqual(query.updated_with["resolution_note"], "Resolved")
        self.assertEqual(query.updated_with["resolved_at"], "now")
        self.assertEqual(query.updated_with["resolved_by_id"], 7)

    def test_close_resolved_query_only_updates_resolved_queries(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        query = _UpdateQuery()
        with patch(
            "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileDataQuery.objects.filter",
            return_value=query,
        ) as filter_query:
            closed = repository.close_resolved_query(
                dataquery_id=101,
                page_state_id=23,
                field_template_id=11,
                actor_user_id=7,
                now="now",
            )

        self.assertIs(closed, True)
        filter_query.assert_called_once_with(
            pk=101,
            page_state_id=23,
            field_template_id=11,
            deleted=False,
            status=ReconcileDataQueryStatusChoices.RESOLVED,
        )
        self.assertEqual(query.updated_with["status"], "closed")
        self.assertEqual(query.updated_with["closed_at"], "now")
        self.assertEqual(query.updated_with["closed_by_id"], 7)

    def test_reopen_query_marks_allowed_queries_open(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        query = _UpdateQuery()
        with patch(
            "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileDataQuery.objects.filter",
            return_value=query,
        ) as filter_query:
            opened = repository.reopen_query(
                dataquery_id=101,
                page_state_id=23,
                field_template_id=11,
                actor_user_id=7,
                now="now",
            )

        self.assertIs(opened, True)
        filter_query.assert_called_once_with(
            pk=101,
            page_state_id=23,
            field_template_id=11,
            deleted=False,
            status__in=(
                ReconcileDataQueryStatusChoices.RESOLVED,
                ReconcileDataQueryStatusChoices.CLOSED,
            ),
        )
        self.assertEqual(query.updated_with["status"], "open")
        self.assertIsNone(query.updated_with["resolved_at"])
        self.assertIsNone(query.updated_with["resolved_by_id"])
        self.assertIsNone(query.updated_with["closed_at"])
        self.assertIsNone(query.updated_with["closed_by_id"])

    def test_request_clarification_only_updates_answered_queries(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        query = _UpdateQuery()
        with patch(
            "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileDataQuery.objects.filter",
            return_value=query,
        ) as filter_query:
            opened = repository.request_clarification(
                dataquery_id=101,
                page_state_id=23,
                field_template_id=11,
                actor_user_id=7,
                now="now",
            )

        self.assertIs(opened, True)
        filter_query.assert_called_once_with(
            pk=101,
            page_state_id=23,
            field_template_id=11,
            deleted=False,
            status=ReconcileDataQueryStatusChoices.ANSWERED,
        )
        self.assertEqual(query.updated_with["status"], "open")
        self.assertIsNone(query.updated_with["answered_at"])
        self.assertIsNone(query.updated_with["answered_by_id"])
        self.assertEqual(query.updated_with["updated_at"], "now")
        self.assertEqual(query.updated_with["updated_by_id"], 7)

    def test_cancel_query_sets_cancelled_status(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        query = _UpdateQuery()
        with patch(
            "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileDataQuery.objects.filter",
            return_value=query,
        ):
            cancelled = repository.cancel_query(
                dataquery_id=101,
                page_state_id=23,
                field_template_id=11,
                actor_user_id=7,
                now="now",
            )

        self.assertIs(cancelled, True)
        self.assertEqual(query.updated_with["status"], "cancelled")
        self.assertEqual(query.updated_with["updated_at"], "now")
        self.assertEqual(query.updated_with["updated_by_id"], 7)

    def test_acknowledge_validation_issue_sets_actor_comment_and_resolution_time(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        issue = _IssueRecord(
            pk=701,
            failed_value="bad",
            severity="warning",
            message="Please acknowledge.",
            data_version=5,
        )
        with (
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssue.objects.select_related",
                return_value=_SelectRelatedQuery(issue),
            ),
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssueSnapshot.objects.create",
            ) as create_snapshot,
        ):
            acknowledged_ids = repository.acknowledge_validation_issues(
                page_state_id=23,
                items=[{"issue_id": 701, "comment": "Reviewed warning."}],
                actor_user_id=7,
                now="now",
                validation_run_id=8801,
            )

        self.assertEqual(acknowledged_ids, [701])
        self.assertEqual(issue.status, ReconcileValidationIssueStatusChoices.ACKNOWLEDGED)
        self.assertEqual(issue.acknowledged_by, 7)
        self.assertEqual(issue.acknowledged_at, "now")
        self.assertEqual(issue.acknowledgement_comment, "Reviewed warning.")
        self.assertEqual(issue.resolved_at, "now")
        self.assertEqual(
            issue.saved_update_fields,
            [
                "status",
                "acknowledged_by",
                "acknowledged_at",
                "acknowledgement_comment",
                "resolved_at",
            ],
        )
        create_snapshot.assert_called_once_with(
            validation_issue_id=701,
            validation_run_id=8801,
            result="PASS",
            evaluated_values_json="bad",
            message="Reviewed warning.",
            severity="warning",
            data_version=5,
            created_at="now",
            related_audit_event_id=None,
        )

    def test_reopen_validation_issue_reactivates_issue_and_records_reopen_snapshot(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        issue = _IssueRecord(
            pk=701,
            failed_value="2.72",
            severity="MAJOR",
            message="Outside range",
            data_version=2,
        )
        issue.status = ReconcileValidationIssueStatusChoices.ACKNOWLEDGED
        issue.acknowledged_by = 23
        issue.acknowledged_at = "earlier"
        issue.acknowledgement_comment = "Reviewed"
        issue.resolved_at = "earlier"
        with (
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssue.objects.select_related",
                return_value=_SelectRelatedQuery(issue),
            ) as select_related,
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.DjangoReconcileDataQueryWriteRepository.create_validation_run",
                return_value=SimpleNamespace(pk=9901),
            ) as create_validation_run,
            patch(
                "apps.reconcile.infrastructure.repositories.dataquery_write.DjangoReconcileDataQueryWriteRepository._create_validation_issue_snapshot",
            ) as create_snapshot,
        ):
            result = repository.reopen_validation_issue(
                issue_id=701,
                page_state_id=23,
                reason="Please answer again.",
                actor_user_id=23,
                now="now",
            )

        self.assertEqual(
            result,
            {
                "issue_id": 701,
                "page_state_id": 23,
                "status": ReconcileValidationIssueStatusChoices.ACKNOWLEDGEMENT_REQUIRED,
                "changed": True,
            },
        )
        select_related.assert_called_once_with("form_instance")
        create_validation_run.assert_called_once_with(
            page_state_id=23,
            source=ReconcileValidationRunSourceChoices.VALIDATION_ISSUE_REOPEN,
            data_version=2,
            actor_user_id=23,
            now="now",
        )
        self.assertEqual(issue.status, ReconcileValidationIssueStatusChoices.ACKNOWLEDGEMENT_REQUIRED)
        self.assertIsNone(issue.acknowledged_by)
        self.assertIsNone(issue.acknowledged_at)
        self.assertIsNone(issue.acknowledgement_comment)
        self.assertIsNone(issue.resolved_at)
        self.assertEqual(
            issue.saved_update_fields,
            [
                "status",
                "acknowledged_by",
                "acknowledged_at",
                "acknowledgement_comment",
                "resolved_at",
            ],
        )
        create_snapshot.assert_called_once_with(
            validation_issue_id=701,
            validation_run_id=9901,
            result=ReconcileValidationIssueSnapshotResultChoices.REOPENED,
            evaluated_values_json={
                "_validation_context": "reopened",
                "value": "2.72",
                "acknowledged": False,
                "reopened": True,
            },
            message="Please answer again.",
            severity="MAJOR",
            data_version=2,
            created_at="now",
            related_audit_event_id=None,
        )

    def test_mark_validation_issue_corrected_sets_corrected_status_and_comment(self):
        repository = DjangoReconcileDataQueryWriteRepository()
        issue = _UpdateQuery()
        with patch(
            "apps.reconcile.infrastructure.repositories.dataquery_write.ReconcileValidationIssue.objects.filter",
            return_value=issue,
        ):
            corrected = repository.mark_validation_issue_corrected(
                issue_id=701,
                page_state_id=23,
                actor_user_id=7,
                correction_comment="Cập nhật dữ liệu từ 8 thành 19",
                now="now",
            )

        self.assertIs(corrected, True)
        self.assertEqual(issue.updated_with["status"], ReconcileValidationIssueStatusChoices.CORRECTED)
        self.assertEqual(issue.updated_with["acknowledged_by"], 7)
        self.assertEqual(issue.updated_with["acknowledged_at"], "now")
        self.assertEqual(issue.updated_with["acknowledgement_comment"], "Cập nhật dữ liệu từ 8 thành 19")
        self.assertEqual(issue.updated_with["resolved_at"], "now")


class _ReconcileRepositoryStub:
    def __init__(self):
        self.created_threads = []
        self.created_soft_issues = []
        self.created_validation_queries = []
        self.created_validation_runs = []
        self.acknowledged_validation_issues = []
        self.reopened_validation_issues = []
        self.validation_issue_scope_calls = []
        self.corrected_validation_issues = []
        self.answered_calls = []

    def list_field_key_to_id(self, *, crf_template_id):
        return {"field_1": 1, "field_2": 2, "field_3": 3}

    def list_latest_open_query_ids_by_page_state_and_field_templates(self, *, page_state_id, field_template_ids):
        self.page_state_id = page_state_id
        self.field_template_ids = field_template_ids
        return {1: 101, 2: 102, 3: 103}

    def list_field_thread_value_contexts(self, *, crf_template_id, field_template_ids):
        return {
            1: {
                "control_type": "radio",
                "options": '{"source":"static","static":[{"label":"Yes","value":"Y"},{"label":"No","value":"N"}]}',
            },
            2: {
                "control_type": "checkbox",
                "options": {
                    "source": "static",
                    "static": [
                        {"label": "Alpha", "value": "A"},
                        {"label": "Beta", "value": "B"},
                    ],
                },
            },
            3: {
                "control_type": "text",
                "options": '{"source":"lookup","static":[{"label":"Ignored","value":"raw value"}]}',
            },
        }

    def mark_query_answered(self, **kwargs):
        self.answered_calls.append(kwargs)
        return True

    def create_query_thread_message(self, **kwargs):
        self.created_threads.append(
            {
                "dataquery_id": kwargs["dataquery_id"],
                "message_text": kwargs["message_text"],
                "message_type": kwargs["message_type"],
                "actor_user_id": kwargs["actor_user_id"],
                "source": kwargs["source"],
            }
        )
        return SimpleNamespace(message_text=kwargs["message_text"], message_type=kwargs["message_type"], created_at=kwargs["now"])

    def bulk_create_soft_validation_issues(self, **kwargs):
        self.created_soft_issues.append(kwargs)
        return len(kwargs["items"])

    def create_validation_run(self, **kwargs):
        self.created_validation_runs.append(kwargs)
        return SimpleNamespace(pk=8801)

    def get_page_state_data_version(self, **kwargs):
        self.page_state_data_version_check = kwargs
        return 5

    def has_open_query_for_page_field(self, **kwargs):
        self.open_query_check = kwargs
        return False

    def create_validation_open_query(self, **kwargs):
        self.created_validation_queries.append(kwargs)
        return SimpleNamespace(pk=901)

    def acknowledge_validation_issues(self, **kwargs):
        self.acknowledged_validation_issues.append(kwargs)
        return [int(item["issue_id"]) for item in kwargs["items"]]

    def get_validation_issue_action_scope(self, **kwargs):
        self.validation_issue_scope_calls.append(kwargs)
        return {
            "issue_id": int(kwargs["issue_id"]),
            "page_state_id": 11,
            "status": ReconcileValidationIssueStatusChoices.ACKNOWLEDGED,
        }

    def reopen_validation_issue(self, **kwargs):
        self.reopened_validation_issues.append(kwargs)
        return {
            "issue_id": kwargs["issue_id"],
            "page_state_id": kwargs["page_state_id"],
            "status": ReconcileValidationIssueStatusChoices.ACKNOWLEDGEMENT_REQUIRED,
            "changed": True,
        }

    def list_active_validation_issues_by_page_state_and_field_templates(self, **kwargs):
        return [{"id": 701, "rule_id": 201, "field_template_id": 1, "failed_value": "8"}]

    def mark_validation_issue_corrected(self, **kwargs):
        self.corrected_validation_issues.append(kwargs)
        return True


class _ReplyRepositoryStub:
    def __init__(self, *, can_respond=True, can_answer=True):
        self.created_threads = []
        self.answered_calls = []
        self.resolved_calls = []
        self.closed_resolved_calls = []
        self.reopen_calls = []
        self.clarification_calls = []
        self.cancelled_calls = []
        self.can_respond = can_respond
        self.can_answer = can_answer

    def query_belongs_to_scope(self, **kwargs):
        self.scope_check = kwargs
        return True

    def user_can_respond_to_query(self, **kwargs):
        self.response_actor_check = kwargs
        return self.can_respond

    def create_query_thread_message(self, **kwargs):
        self.created_threads.append(kwargs)
        return SimpleNamespace(
            message_text=kwargs["message_text"],
            message_type=kwargs["message_type"],
            created_at=kwargs["now"],
        )

    def mark_query_answered(self, **kwargs):
        self.answered_calls.append(kwargs)
        return self.can_answer

    def resolve_query(self, **kwargs):
        self.resolved_calls.append(kwargs)
        return True

    def close_resolved_query(self, **kwargs):
        self.closed_resolved_calls.append(kwargs)
        return True

    def reopen_query(self, **kwargs):
        self.reopen_calls.append(kwargs)
        return True

    def request_clarification(self, **kwargs):
        self.clarification_calls.append(kwargs)
        return True

    def cancel_query(self, **kwargs):
        self.cancelled_calls.append(kwargs)
        return True


class _ReconcileRepositoryWithEntryContext(DjangoReconcileDataQueryWriteRepository):
    @classmethod
    def _current_page_entry_query_context(cls, *, page_state_id, field_template_id, storage_key_hint=""):
        return {
            "page_entry_id": 301,
            "value_snapshot": "1",
            "field_path": "$.CONTRACEPT_YN",
            "data_version": "v2",
            "assigned_to_id": 42,
        }


class _UpdateQuery:
    def __init__(self):
        self.updated_with = None

    def exclude(self, **kwargs):
        self.excluded_with = kwargs
        return self

    def update(self, **kwargs):
        self.updated_with = kwargs
        return 1


class _IssueRecord:
    def __init__(self, *, pk, failed_value, severity, message, data_version):
        self.pk = pk
        self.failed_value = failed_value
        self.severity = severity
        self.message = message
        self.form_instance = SimpleNamespace(data_version=data_version)
        self.status = None
        self.acknowledged_by = None
        self.acknowledged_at = None
        self.acknowledgement_comment = None
        self.resolved_at = None
        self.saved_update_fields = None

    def save(self, *, update_fields):
        self.saved_update_fields = list(update_fields)


class _SelectRelatedQuery:
    def __init__(self, issue):
        self.issue = issue

    def filter(self, **kwargs):
        self.filtered_with = kwargs
        return self

    def first(self):
        return self.issue
