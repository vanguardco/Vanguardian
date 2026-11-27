import django_tables2 as tables
from django.core.exceptions import ObjectDoesNotExist
from django.utils.html import format_html_join
from django.utils.translation import gettext_lazy as _

from apps.shared.datetime_formatting import date_format
from apps.subject.presentation.web.mappers.participation_status import (
    get_subject_participation_status_label,
)
from apps.subject.presentation.web.mappers.subject_list_model import get_subject_list_row_model


def _subject_detail_row_href(table, record):
    return table.detail_url_by_subject_id.get(record.pk, "")


class SubjectListTable(tables.Table):
    screening_code = tables.Column(
        verbose_name=_("SCREENING CODE"),
        attrs={
            "th": {"class": "subject-list-table__code-column"},
            "td": {
                "class": "entity-table__primary subject-list-table__code-column"
            },
        },
    )
    enrollment = tables.Column(
        empty_values=(),
        verbose_name=_("Enrollment"),
        orderable=False,
    )
    lifecycle_status = tables.Column(
        verbose_name=_("Participation"),
        order_by=("lifecycle_status", "current_sequence", "id"),
    )
    randomization_code = tables.Column(
        empty_values=(),
        verbose_name=_("Randomization Code"),
        orderable=False,
        attrs={
            "th": {"class": "subject-list-table__code-column"},
            "td": {
                "class": "entity-table__primary subject-list-table__code-column"
            },
        },
    )
    randomization = tables.Column(
        empty_values=(),
        verbose_name=_("Randomization"),
        orderable=False,
    )
    arm = tables.Column(
        empty_values=(),
        verbose_name=_("ARM"),
        orderable=False,
    )
    completion = tables.Column(
        empty_values=(),
        verbose_name=_("Completion"),
        orderable=False,
    )
    open_queries = tables.Column(
        empty_values=(),
        verbose_name=_("Open Queries"),
        orderable=False,
    )
    validation_issues = tables.Column(
        empty_values=(),
        verbose_name=_("Validation Issues"),
        orderable=False,
    )
    actions = tables.TemplateColumn(
        template_name="subject/includes/subject_list_actions_loader_cell.html",
        verbose_name=_("ACTIONS"),
        empty_values=(),
        orderable=False,
        attrs={"td": {"class": "entity-table__actions"}},
    )

    def __init__(self, *args, **kwargs):
        verify_show_by_subject_id = kwargs.pop("verify_show_by_subject_id", None)
        current_treatment_by_subject_id = kwargs.pop(
            "current_treatment_by_subject_id",
            None,
        )
        workflow_action_event_id_by_subject_id = kwargs.pop(
            "workflow_action_event_id_by_subject_id",
            None,
        )
        detail_url_by_subject_id = kwargs.pop("detail_url_by_subject_id", None)
        self.randomization_transition_facts = (
            kwargs.pop("randomization_transition_facts", None) or {}
        )
        self.can_update_subject = kwargs.pop("can_update_subject", False)
        self.can_early_terminate = kwargs.pop("can_early_terminate", False)
        early_termination_eligible_subject_ids = kwargs.pop(
            "early_termination_eligible_subject_ids",
            (),
        )
        self.bind_runtime_context(
            verify_show_by_subject_id=verify_show_by_subject_id,
            current_treatment_by_subject_id=current_treatment_by_subject_id,
            workflow_action_event_id_by_subject_id=(
                workflow_action_event_id_by_subject_id
            ),
            detail_url_by_subject_id=detail_url_by_subject_id,
            early_termination_eligible_subject_ids=(
                early_termination_eligible_subject_ids
            ),
        )
        super().__init__(*args, **kwargs)

    def bind_runtime_context(
        self,
        *,
        verify_show_by_subject_id=None,
        current_treatment_by_subject_id=None,
        workflow_action_event_id_by_subject_id=None,
        detail_url_by_subject_id=None,
        early_termination_eligible_subject_ids=(),
    ):
        self._verify_show_by_subject_id = verify_show_by_subject_id or {}
        self._current_treatment_by_subject_id = (
            current_treatment_by_subject_id or {}
        )
        self.workflow_action_event_id_by_subject_id = (
            workflow_action_event_id_by_subject_id or {}
        )
        self.detail_url_by_subject_id = detail_url_by_subject_id or {}
        self.early_termination_eligible_subject_ids = frozenset(
            early_termination_eligible_subject_ids
        )
        self.verify_eligible_subject_ids = frozenset(
            subject_id
            for subject_id, is_eligible in self._verify_show_by_subject_id.items()
            if is_eligible
        )

    def render_enrollment(self, record):
        try:
            is_enrolled = record.enrollment.is_enrolled
            enrollment_date = record.enrollment.enrollment_date
        except ObjectDoesNotExist:
            return "—"
        if not is_enrolled or not enrollment_date:
            return "—"
        return date_format(enrollment_date, "DATE_FORMAT")

    def render_lifecycle_status(self, record):
        return get_subject_participation_status_label(
            record,
            randomization_transition_facts=self.randomization_transition_facts,
        )

    def render_randomization(self, record):
        try:
            created_at = record.randomization.created_at
        except ObjectDoesNotExist:
            return "—"
        return date_format(created_at, "DATETIME_FORMAT") if created_at else "—"

    @staticmethod
    def render_randomization_code(record):
        try:
            return record.randomization.randomization_number or "—"
        except (AttributeError, ObjectDoesNotExist):
            return "—"

    def render_arm(self, record):
        current_treatment = self._current_treatment_by_subject_id.get(record.pk)
        return (
            getattr(current_treatment, "treatment_code", None)
            or getattr(current_treatment, "last_treatment", None)
            or "—"
        )

    @staticmethod
    def render_completion(record):
        return "—"

    @staticmethod
    def render_open_queries(record):
        return int(getattr(record, "open_query_count", 0) or 0)

    @staticmethod
    def render_validation_issues(record):
        return int(getattr(record, "validation_issue_count", 0) or 0)

    class Meta:
        model = get_subject_list_row_model()
        row_attrs = {
            "data-detail-href": _subject_detail_row_href,
        }
        fields = (
            "screening_code",
            "enrollment",
            "lifecycle_status",
            "randomization_code",
            "randomization",
            "arm",
            "completion",
            "open_queries",
            "validation_issues",
            "actions",
        )


class SubjectAuditHistoryTable(tables.Table):
    occurred_at = tables.Column(verbose_name=_("Time"))
    source = tables.Column(verbose_name=_("Source"))
    field_name = tables.Column(verbose_name=_("Field Name"), attrs={"td": {"class": "entity-table__primary"}})
    field_description = tables.Column(verbose_name=_("Field Description"))
    value = tables.Column(verbose_name=_("Value"), orderable=False)
    user_display = tables.Column(verbose_name=_("User"))
    details = tables.Column(verbose_name=_("Details"), empty_values=(), orderable=False)

    @staticmethod
    def render_occurred_at(value):
        return date_format(value, "DATETIME_FORMAT") if value else "—"

    @staticmethod
    def render_source(value):
        return value or "—"

    @staticmethod
    def render_field_name(value):
        return value or "—"

    @staticmethod
    def render_field_description(value):
        return value or "—"

    @staticmethod
    def render_value(value):
        return value or "—"

    @staticmethod
    def render_user_display(value):
        return value or "—"

    @staticmethod
    def render_details(record):
        details = record.get("details", []) if isinstance(record, dict) else getattr(record, "details", [])
        reason = record.get("reason", "") if isinstance(record, dict) else getattr(record, "reason", "")
        rows = []
        if reason:
            rows.append(("Reason", reason))
        rows.extend(
            (detail.get("label"), detail.get("value"))
            for detail in details
            if detail.get("label") and detail.get("value")
        )
        if not rows:
            return "—"
        return format_html_join(
            "",
            '<div class="subject-audit-workbench__detail"><strong>{}</strong><span>{}</span></div>',
            rows,
        )

    class Meta:
        attrs = {"class": "entity-table"}
        order_by = ("-occurred_at",)
        fields = (
            "occurred_at",
            "source",
            "field_name",
            "field_description",
            "value",
            "user_display",
            "details",
        )


__all__ = [
    "SubjectAuditHistoryTable",
    "SubjectListTable",
]
