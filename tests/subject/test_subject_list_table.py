from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.subject.presentation.web.tables import SubjectAuditHistoryTable, SubjectListTable


class SubjectListTableTests(SimpleTestCase):
    def test_participation_shows_screen_failure_instead_of_active(self):
        record = SimpleNamespace(
            pk=1,
            lifecycle_status="active",
            enrollment=SimpleNamespace(
                status="ScreenFailure",
                is_enrolled=False,
                deleted=False,
            ),
            get_lifecycle_status_display=lambda: "Active",
        )
        table = SubjectListTable([record])

        self.assertEqual(str(table.render_lifecycle_status(record)), "Screen Failure")

    def test_subject_audit_history_table_has_workbench_columns(self):
        table = SubjectAuditHistoryTable([])

        self.assertEqual(
            table.columns.names(),
            [
                "occurred_at",
                "source",
                "field_name",
                "field_description",
                "value",
                "user_display",
                "details",
            ],
        )

    def test_subject_list_table_shows_randomization_code_and_current_treatment(self):
        record = SimpleNamespace(
            pk=1,
            study_id=10,
            subject_code="SUBJ-001",
            screening_code="SCR-001",
            created_at=None,
            randomization=SimpleNamespace(
                created_at=None,
                randomization_number="NNG31-019",
            ),
            open_query_count=3,
            validation_issue_count=2,
        )
        table = SubjectListTable(
            [record],
            verify_show_by_subject_id={},
            current_treatment_by_subject_id={1: SimpleNamespace(treatment_code="EPREX_4000U")},
            workflow_action_event_id_by_subject_id={},
            can_update_subject=False,
        )

        self.assertNotIn("subject_code", table.columns.names())
        self.assertIn("randomization_code", table.columns.names())
        self.assertIn("arm", table.columns.names())
        self.assertIn("open_queries", table.columns.names())
        self.assertIn("validation_issues", table.columns.names())
        self.assertNotIn("current_visit", table.columns.names())
        self.assertNotIn("query_status", table.columns.names())
        self.assertIn("screening_code", table.columns.names())
        self.assertNotIn("screening", table.columns.names())
        self.assertLess(
            table.columns.names().index("randomization_code"),
            table.columns.names().index("randomization"),
        )
        self.assertLess(
            table.columns.names().index("randomization"),
            table.columns.names().index("arm"),
        )
        self.assertLess(table.columns.names().index("arm"), table.columns.names().index("completion"))
        self.assertEqual(str(table.columns["arm"].header), "ARM")
        self.assertEqual(str(table.columns["open_queries"].header), "Open Queries")
        self.assertEqual(str(table.columns["validation_issues"].header), "Validation Issues")
        self.assertEqual(str(table.columns["randomization_code"].header), "Randomization Code")
        for column_name in ("screening_code", "randomization_code"):
            attrs = table.columns[column_name].column.attrs
            self.assertIn("subject-list-table__code-column", attrs["th"]["class"])
            self.assertIn("subject-list-table__code-column", attrs["td"]["class"])
        self.assertEqual(table.render_randomization_code(record), "NNG31-019")
        self.assertEqual(table.render_arm(record), "EPREX_4000U")
        self.assertEqual(table.render_open_queries(record), 3)
        self.assertEqual(table.render_validation_issues(record), 2)

    def test_subject_list_table_arm_falls_back_to_dash_when_missing(self):
        record = SimpleNamespace(pk=1)
        table = SubjectListTable(
            [record],
            verify_show_by_subject_id={},
            workflow_action_event_id_by_subject_id={},
            can_update_subject=False,
        )

        self.assertEqual(table.render_arm(record), "—")
        self.assertEqual(table.render_randomization_code(record), "—")

    def test_subject_list_table_arm_shows_period_1_treatment_during_washout(self):
        record = SimpleNamespace(pk=1)
        table = SubjectListTable(
            [record],
            verify_show_by_subject_id={},
            current_treatment_by_subject_id={
                1: SimpleNamespace(
                    treatment_code=None,
                    last_treatment="NANOKINE",
                    next_treatment="EPREX_4000U",
                )
            },
            workflow_action_event_id_by_subject_id={},
            can_update_subject=False,
        )

        self.assertEqual(table.render_arm(record), "NANOKINE")
