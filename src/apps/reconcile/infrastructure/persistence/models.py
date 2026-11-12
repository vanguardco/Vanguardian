from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.choices.reconcile import ReconcileValidationRunSourceChoices


class ReconcileDataQueryStatusChoices(models.TextChoices):
    OPEN = "open", _("Open")
    ANSWERED = "answered", _("Answered")
    RESOLVED = "resolved", _("Resolved")
    CLOSED = "closed", _("Closed")
    CANCELLED = "cancelled", _("Cancelled")


class ReconcileDataQuerySourceChoices(models.TextChoices):
    MANUAL = "manual", _("Manual")
    SYSTEM = "system", _("System")
    IMPORT = "import", _("Import")


class ReconcileDataQueryTypeChoices(models.TextChoices):
    MANUAL = "manual", _("Manual")
    VALIDATION = "validation", _("Validation")
    SDV = "sdv", _("SDV")
    MEDICAL = "medical", _("Medical")
    ELIGIBILITY = "eligibility", _("Eligibility")
    SYSTEM = "system", _("System")


class ReconcileDataQuerySeverityChoices(models.TextChoices):
    MINOR = "minor", _("Minor")
    MAJOR = "major", _("Major")
    CRITICAL = "critical", _("Critical")


class ReconcileQueryThreadMessageTypeChoices(models.TextChoices):
    COMMENT = "comment", _("Comment")
    STATUS_CHANGE = "status_change", _("Status Change")
    RESOLUTION = "resolution", _("Resolution")


class ReconcileQueryThreadVisibilityChoices(models.TextChoices):
    SITE = "site", _("Site")
    SPONSOR = "sponsor", _("Sponsor")
    INTERNAL = "internal", _("Internal")


class ReconcileQueryThreadSourceChoices(models.TextChoices):
    MANUAL = "manual", _("Manual")
    SYSTEM = "system", _("System")
    IMPORT = "import", _("Import")


class ReconcileValidationIssueStatusChoices(models.TextChoices):
    OPEN = "OPEN", _("Open")
    ACKNOWLEDGEMENT_REQUIRED = "ACKNOWLEDGEMENT_REQUIRED", _("Acknowledgement required")
    ACKNOWLEDGED = "ACKNOWLEDGED", _("Acknowledged")
    CORRECTED = "CORRECTED", _("Corrected")
    QUERY_CREATED = "QUERY_CREATED", _("Query created")
    CLOSED = "CLOSED", _("Closed")
    WAIVED = "WAIVED", _("Waived")


class ReconcileValidationIssueSnapshotResultChoices(models.TextChoices):
    FAIL = "FAIL", _("Fail")
    PASS = "PASS", _("Pass")
    REOPENED = "REOPENED", _("Reopened")


class ReconcileDataQuery(models.Model):
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    deleted = models.BooleanField(default=False)

    status = models.CharField(
        max_length=32,
        choices=ReconcileDataQueryStatusChoices.choices,
    )
    source = models.CharField(
        max_length=16,
        choices=ReconcileDataQuerySourceChoices.choices,
    )
    query_type = models.CharField(
        max_length=32,
        choices=ReconcileDataQueryTypeChoices.choices,
    )
    severity = models.CharField(
        max_length=16,
        choices=ReconcileDataQuerySeverityChoices.choices,
        default=ReconcileDataQuerySeverityChoices.MINOR,
    )
    is_blocking = models.BooleanField(default=True)

    question_text = models.TextField()
    resolution_note = models.CharField(max_length=1000, null=True, blank=True)

    opened_at = models.DateTimeField()
    answered_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    reason_code = models.CharField(max_length=64, null=True, blank=True)

    page_state = models.ForeignKey(
        "datacapture.DataCapturePageState",
        on_delete=models.DO_NOTHING,
        db_column="page_state_id",
        related_name="reconcile_data_queries",
    )
    page_entry = models.ForeignKey(
        "datacapture.DataCapturePageEntry",
        on_delete=models.DO_NOTHING,
        db_column="page_entry_id",
        related_name="reconcile_data_queries",
        null=True,
        blank=True,
    )
    field_template = models.ForeignKey(
        "crf.CrfFieldTemplate",
        on_delete=models.DO_NOTHING,
        db_column="field_template_id",
        related_name="reconcile_data_queries",
        null=True,
        blank=True,
    )
    validation_rule = models.ForeignKey(
        "crf.CrfFieldValidationRule",
        on_delete=models.DO_NOTHING,
        db_column="validation_rule_id",
        related_name="reconcile_data_queries",
        null=True,
        blank=True,
    )
    data_version = models.CharField(max_length=16, null=True, blank=True)
    field_path = models.CharField(max_length=512, null=True, blank=True)
    value_snapshot = models.TextField(null=True, blank=True)

    assigned_to_id = models.BigIntegerField(null=True, blank=True)
    opened_by_id = models.BigIntegerField(null=True, blank=True)
    answered_by_id = models.BigIntegerField(null=True, blank=True)
    resolved_by_id = models.BigIntegerField(null=True, blank=True)
    closed_by_id = models.BigIntegerField(null=True, blank=True)
    created_by_id = models.BigIntegerField(null=True, blank=True)
    updated_by_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "reconcile_dataquery"
        managed = True
        default_permissions = ()
        indexes = [
            models.Index(fields=["page_state"], name="recon_dq_page_state_idx"),
            models.Index(fields=["field_template"], name="recon_dq_field_tpl_idx"),
            models.Index(fields=["validation_rule"], name="recon_dq_val_rule_idx"),
            models.Index(fields=["status"], name="recon_dq_status_idx"),
            models.Index(fields=["source"], name="recon_dq_source_idx"),
            models.Index(fields=["page_state", "status"], name="recon_dq_page_status_idx"),
            models.Index(
                fields=["page_state", "is_blocking", "status"],
                name="recon_dq_page_block_st_idx",
            ),
            models.Index(fields=["field_template", "status"], name="recon_dq_field_status_idx"),
            models.Index(fields=["assigned_to_id", "status"], name="recon_dq_assignee_st_idx"),
        ]
        verbose_name = "reconcile data query"
        verbose_name_plural = "reconcile data queries"


class ReconcileQueryThread(models.Model):
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    deleted = models.BooleanField(default=False)

    message_text = models.TextField()
    message_type = models.CharField(
        max_length=16,
        choices=ReconcileQueryThreadMessageTypeChoices.choices,
        default=ReconcileQueryThreadMessageTypeChoices.COMMENT,
    )
    visibility = models.CharField(
        max_length=16,
        choices=ReconcileQueryThreadVisibilityChoices.choices,
        default=ReconcileQueryThreadVisibilityChoices.SITE,
    )
    source = models.CharField(
        max_length=16,
        choices=ReconcileQueryThreadSourceChoices.choices,
        default=ReconcileQueryThreadSourceChoices.MANUAL,
    )

    dataquery = models.ForeignKey(
        ReconcileDataQuery,
        on_delete=models.DO_NOTHING,
        db_column="dataquery_id",
        related_name="query_threads",
    )
    author_id = models.BigIntegerField(null=True, blank=True)
    created_by_id = models.BigIntegerField(null=True, blank=True)
    updated_by_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "reconcile_query_thread"
        managed = True
        default_permissions = ()
        indexes = [
            models.Index(fields=["dataquery", "created_at"], name="recon_qthread_query_time_idx"),
        ]
        verbose_name = "reconcile query thread"
        verbose_name_plural = "reconcile query threads"


class ReconcileValidationIssue(models.Model):
    created_at = models.DateTimeField()

    rule = models.ForeignKey(
        "crf.CrfFieldValidationRule",
        on_delete=models.DO_NOTHING,
        db_column="rule_id",
        related_name="reconcile_validation_issues",
    )
    form_instance = models.ForeignKey(
        "datacapture.DataCapturePageState",
        on_delete=models.DO_NOTHING,
        db_column="form_instance_id",
        related_name="reconcile_validation_issues",
    )
    field_instance = models.ForeignKey(
        "datacapture.DataCaptureFieldEntry",
        on_delete=models.DO_NOTHING,
        db_column="field_instance_id",
        related_name="reconcile_validation_issues",
        null=True,
        blank=True,
    )

    mode = models.CharField(max_length=30)
    severity = models.CharField(max_length=30)
    status = models.CharField(
        max_length=50,
        choices=ReconcileValidationIssueStatusChoices.choices,
    )

    message = models.TextField()
    failed_value = models.JSONField(null=True, blank=True)

    acknowledged_by = models.BigIntegerField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_comment = models.TextField(null=True, blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "reconcile_validation_issue"
        managed = True
        default_permissions = ()
        indexes = [
            models.Index(fields=["form_instance", "status"], name="recon_vi_form_status_idx"),
            models.Index(fields=["rule", "form_instance", "status"], name="recon_vi_rule_form_st_idx"),
            models.Index(fields=["field_instance", "status"], name="recon_vi_field_status_idx"),
        ]
        verbose_name = "reconcile validation issue"
        verbose_name_plural = "reconcile validation issues"


class ReconcileValidationRun(models.Model):
    created_at = models.DateTimeField()

    form_instance = models.ForeignKey(
        "datacapture.DataCapturePageState",
        on_delete=models.DO_NOTHING,
        db_column="form_instance_id",
        related_name="reconcile_validation_runs",
    )
    source = models.CharField(
        max_length=32,
        choices=ReconcileValidationRunSourceChoices.choices,
    )
    data_version = models.BigIntegerField()
    triggered_by = models.BigIntegerField(null=True, blank=True)
    related_audit_event = models.ForeignKey(
        "audit.AuditEvent",
        on_delete=models.DO_NOTHING,
        db_column="related_audit_event_id",
        related_name="reconcile_validation_runs",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "reconcile_validation_run"
        managed = True
        default_permissions = ()
        indexes = [
            models.Index(fields=["form_instance", "created_at"], name="recon_vi_run_form_time_idx"),
            models.Index(fields=["source", "created_at"], name="recon_vi_run_source_time_idx"),
        ]
        verbose_name = "reconcile validation run"
        verbose_name_plural = "reconcile validation runs"


class ReconcileValidationIssueSnapshot(models.Model):
    created_at = models.DateTimeField()

    validation_issue = models.ForeignKey(
        ReconcileValidationIssue,
        on_delete=models.DO_NOTHING,
        db_column="validation_issue_id",
        related_name="snapshots",
    )
    validation_run = models.ForeignKey(
        ReconcileValidationRun,
        on_delete=models.DO_NOTHING,
        db_column="validation_run_id",
        related_name="snapshots",
    )
    result = models.CharField(
        max_length=16,
        choices=ReconcileValidationIssueSnapshotResultChoices.choices,
    )
    evaluated_values_json = models.JSONField(default=dict)
    message = models.TextField()
    severity = models.CharField(max_length=30)
    data_version = models.BigIntegerField()
    related_audit_event = models.ForeignKey(
        "audit.AuditEvent",
        on_delete=models.DO_NOTHING,
        db_column="related_audit_event_id",
        related_name="reconcile_validation_issue_snapshots",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "reconcile_validation_issue_snapshot"
        managed = True
        default_permissions = ()
        indexes = [
            models.Index(
                fields=["validation_issue", "created_at"],
                name="recon_vi_snap_issue_time_idx",
            ),
            models.Index(fields=["validation_run"], name="recon_vi_snap_run_idx"),
            models.Index(
                fields=["validation_issue", "validation_run"],
                name="recon_vi_snap_issue_run_idx",
            ),
        ]
        verbose_name = "reconcile validation issue snapshot"
        verbose_name_plural = "reconcile validation issue snapshots"


__all__ = [
    "ReconcileDataQuery",
    "ReconcileDataQuerySeverityChoices",
    "ReconcileDataQuerySourceChoices",
    "ReconcileDataQueryStatusChoices",
    "ReconcileDataQueryTypeChoices",
    "ReconcileQueryThread",
    "ReconcileQueryThreadMessageTypeChoices",
    "ReconcileQueryThreadSourceChoices",
    "ReconcileQueryThreadVisibilityChoices",
    "ReconcileValidationIssue",
    "ReconcileValidationRun",
    "ReconcileValidationRunSourceChoices",
    "ReconcileValidationIssueSnapshot",
    "ReconcileValidationIssueSnapshotResultChoices",
    "ReconcileValidationIssueStatusChoices",
]
