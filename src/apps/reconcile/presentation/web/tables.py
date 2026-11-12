import django_tables2 as tables
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.shared.datetime_formatting import date_format


class QueryWorkbenchTable(tables.Table):
    query_id = tables.Column(verbose_name=_("Query ID"), attrs={"td": {"class": "entity-table__primary"}})
    status = tables.Column(verbose_name=_("Status"))
    pending_with = tables.Column(verbose_name=_("Pending With"), orderable=False)
    subject = tables.Column(empty_values=(), verbose_name=_("Subject"), orderable=False)
    visit = tables.Column(empty_values=(), verbose_name=_("Visit/Event"), orderable=False)
    crf_page_label = tables.Column(verbose_name=_("CRF Page"), orderable=False)
    field_label_or_path = tables.Column(verbose_name=_("Field"), orderable=False)
    question_text_excerpt = tables.Column(verbose_name=_("Question / Latest Message"), orderable=False)
    reply_count = tables.Column(verbose_name=_("Replies"), orderable=False)
    severity = tables.Column(verbose_name=_("Severity"))
    is_blocking = tables.Column(verbose_name=_("Blocking"))
    source = tables.Column(verbose_name=_("Source"))
    opened_at = tables.Column(verbose_name=_("Opened"))
    last_activity_at = tables.Column(verbose_name=_("Last Activity"))
    assigned_to_display = tables.Column(verbose_name=_("Assigned To"), orderable=False)
    opened_by_display = tables.Column(verbose_name=_("Opened By"), orderable=False)
    actions = tables.TemplateColumn(
        template_name="reconcile/includes/query_workbench_actions_cell.html",
        verbose_name=_("Actions"),
        empty_values=(),
        orderable=False,
        attrs={"td": {"class": "entity-table__actions"}},
    )

    @staticmethod
    def render_query_id(value, record):
        return format_html('<a href="{}">DQ-{}</a>', record.detail_url, value)

    @staticmethod
    def render_status(value):
        return str(value or "—").replace("_", " ").title()

    @staticmethod
    def render_subject(record):
        return record.subject_code or record.screening_code or "—"

    @staticmethod
    def render_visit(record):
        label = record.event_label or record.event_code
        return label or "—"

    @staticmethod
    def render_is_blocking(value):
        return _("Yes") if value else _("No")

    @staticmethod
    def render_opened_at(value):
        return date_format(value, "DATETIME_FORMAT") if value else "—"

    @staticmethod
    def render_last_activity_at(value):
        return date_format(value, "DATETIME_FORMAT") if value else "—"

    class Meta:
        attrs = {"class": "entity-table"}
        fields = (
            "query_id",
            "status",
            "pending_with",
            "subject",
            "visit",
            "crf_page_label",
            "field_label_or_path",
            "question_text_excerpt",
            "reply_count",
            "severity",
            "is_blocking",
            "source",
            "opened_at",
            "last_activity_at",
            "assigned_to_display",
            "opened_by_display",
            "actions",
        )


class ValidationIssueWorkbenchTable(tables.Table):
    issue_id = tables.Column(verbose_name=_("Issue ID"), attrs={"td": {"class": "entity-table__primary"}})
    status = tables.Column(verbose_name=_("Status"))
    severity = tables.Column(verbose_name=_("Severity"))
    subject = tables.Column(empty_values=(), verbose_name=_("Subject"), orderable=False)
    visit = tables.Column(empty_values=(), verbose_name=_("Visit/Event"), orderable=False)
    crf_page_label = tables.Column(verbose_name=_("CRF Page"), orderable=False)
    field_label = tables.Column(verbose_name=_("Field"), orderable=False)
    message = tables.Column(verbose_name=_("Message"), orderable=False)
    failed_value = tables.Column(verbose_name=_("Failed Value"), orderable=False)
    created_at = tables.Column(verbose_name=_("Opened"))
    acknowledged_by_display = tables.Column(verbose_name=_("Acknowledged By"), orderable=False)
    acknowledged_at = tables.Column(verbose_name=_("Acknowledged"), orderable=False)
    actions = tables.TemplateColumn(
        template_name="reconcile/includes/validation_issue_workbench_actions_cell.html",
        verbose_name=_("Actions"),
        empty_values=(),
        orderable=False,
        attrs={"td": {"class": "entity-table__actions"}},
    )

    @staticmethod
    def render_issue_id(value, record):
        if not record.review_focus_url:
            return f"VI-{value}"
        return format_html('<a href="{}">VI-{}</a>', record.review_focus_url, value)

    @staticmethod
    def render_status(value):
        return str(value or "—").replace("_", " ").title()

    @staticmethod
    def render_subject(record):
        return record.subject_code or record.screening_code or "—"

    @staticmethod
    def render_visit(record):
        return record.event_label or "—"

    @staticmethod
    def render_failed_value(value):
        return value if value not in (None, "") else "—"

    @staticmethod
    def render_created_at(value):
        return date_format(value, "DATETIME_FORMAT") if value else "—"

    @staticmethod
    def render_acknowledged_at(value):
        return date_format(value, "DATETIME_FORMAT") if value else "—"

    class Meta:
        attrs = {"class": "entity-table"}
        fields = (
            "issue_id",
            "status",
            "severity",
            "subject",
            "visit",
            "crf_page_label",
            "field_label",
            "message",
            "failed_value",
            "created_at",
            "acknowledged_by_display",
            "acknowledged_at",
            "actions",
        )


__all__ = ["QueryWorkbenchTable", "ValidationIssueWorkbenchTable"]
