from dataclasses import dataclass

from django.urls import reverse
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

from apps.reconcile.infrastructure.repositories import DjangoReconcileDataQueryReadRepository

QUERY_WORKBENCH_BUCKETS = (
    "all",
    "open",
    "awaiting_site",
    "awaiting_review",
    "blocking",
    "resolved",
    "closed",
    "validation_issues",
)


@dataclass(frozen=True)
class QueryWorkbenchSummaryDTO:
    total: int
    open: int
    awaiting_site_response: int
    awaiting_review: int
    blocking_open: int
    resolved: int
    closed: int
    validation_issues_open: int
    hard_validation_issues_open: int
    actionable_for_current_user: int


@dataclass(frozen=True)
class QueryListItemDTO:
    query_id: int
    study_id: int | None
    site_id: int | None
    subject_id: int | None
    status: str
    normalized_bucket: str
    pending_with: str
    source: str
    query_type: str
    severity: str
    is_blocking: bool
    question_text_excerpt: str
    resolution_note: str
    field_path: str
    value_snapshot_excerpt: str
    opened_at: object
    answered_at: object
    resolved_at: object
    closed_at: object
    last_activity_at: object
    reply_count: int
    assigned_to_display: str
    opened_by_display: str
    subject_code: str
    screening_code: str
    subject_display_code: str
    event_code: str
    event_label: str
    crf_page_label: str
    field_label_or_path: str
    review_focus_url: str
    page_state_label: str
    detail_url: str


@dataclass(frozen=True)
class ValidationIssueListItemDTO:
    issue_id: int
    study_id: int | None
    site_id: int | None
    subject_id: int | None
    page_state_id: int
    status: str
    severity: str
    message: str
    failed_value: object
    created_at: object
    resolved_at: object
    acknowledged_at: object
    acknowledged_by_display: str
    subject_code: str
    screening_code: str
    event_label: str
    crf_page_label: str
    field_label: str
    review_focus_url: str
    page_state_label: str


@dataclass(frozen=True)
class QueryThreadDTO:
    id: int
    message_text: str
    message_type: str
    visibility: str
    source: str
    author_display: str
    created_at: object


@dataclass(frozen=True)
class QueryWorkbenchResultDTO:
    summary: QueryWorkbenchSummaryDTO
    items: list[QueryListItemDTO]
    validation_issues: list[ValidationIssueListItemDTO]


class QueryWorkbenchReader:
    def __init__(self, repository=None):
        self.repository = repository or DjangoReconcileDataQueryReadRepository()

    def read(
        self,
        *,
        study_id: int,
        site_id: int | None,
        current_user_id: int | None,
        can_view_internal_thread: bool,
        bucket: str = "all",
        search: str = "",
        status: str = "",
        severity: str = "",
        source: str = "",
        blocking: str = "",
        assigned_to_id: int | None = None,
        opened_by_id: int | None = None,
        sort: str = "-last_activity_at",
    ) -> QueryWorkbenchResultDTO:
        from apps.datacapture.public import list_page_state_contexts_for_study_site

        bucket = bucket if bucket in QUERY_WORKBENCH_BUCKETS else "all"
        contexts = list_page_state_contexts_for_study_site(study_id=study_id, site_id=site_id)
        contexts, query_search = self._filter_contexts_for_search(contexts, search)
        page_state_ids = tuple(sorted(contexts))
        summary = QueryWorkbenchSummaryDTO(**self.repository.summarize_workbench(page_state_ids=page_state_ids))
        rows = self.repository.list_workbench_queries(
            page_state_ids=page_state_ids,
            bucket=bucket,
            search=query_search,
            status=status,
            severity=severity,
            source=source,
            blocking=blocking,
            assigned_to_id=assigned_to_id,
            opened_by_id=opened_by_id,
            sort=sort,
            can_view_internal_thread=can_view_internal_thread,
        )
        issues = []
        if bucket == "validation_issues":
            issues = self.repository.list_workbench_validation_issues(
                page_state_ids=page_state_ids,
                search=query_search,
                severity=severity,
            )
        user_ids = self._row_user_ids(rows)
        user_ids.update(issue.get("acknowledged_by_id") for issue in issues)
        user_display_by_id = self._user_display_map(user_ids)
        return QueryWorkbenchResultDTO(
            summary=summary,
            items=[self._to_query_item(row, contexts, user_display_by_id=user_display_by_id) for row in rows],
            validation_issues=[self._to_validation_issue_item(row, contexts, user_display_by_id=user_display_by_id) for row in issues],
        )

    def read_detail(
        self,
        *,
        query_id: int,
        can_view_internal_thread: bool,
    ) -> tuple[QueryListItemDTO, list[QueryThreadDTO]] | None:
        from apps.datacapture.public import get_page_state_contexts

        row = self.repository.get_workbench_query_detail(
            query_id=query_id,
            can_view_internal_thread=can_view_internal_thread,
        )
        if row is None:
            return None
        contexts = get_page_state_contexts(page_state_ids=[int(row["page_state_id"])])
        raw_threads = row.get("threads", [])
        user_display_by_id = self._user_display_map(self._row_user_ids([row]) | {thread.get("author_id") for thread in raw_threads})
        item = self._to_query_item(row, contexts, user_display_by_id=user_display_by_id)
        threads = [
            QueryThreadDTO(
                id=thread["id"],
                message_text=thread["message_text"],
                message_type=thread["message_type"],
                visibility=thread["visibility"],
                source=thread["source"],
                author_display=self._user_display(thread["author_id"], user_display_by_id),
                created_at=thread["created_at"],
            )
            for thread in raw_threads
        ]
        return item, threads

    @staticmethod
    def pending_with(status: str) -> str:
        normalized = str(status or "").strip().lower()
        if normalized == "open":
            return str(_("Site / Data Entry"))
        if normalized == "answered":
            return str(_("CRA / Data Manager"))
        if normalized == "resolved":
            return str(_("Data Manager / Close"))
        return "—"

    @classmethod
    def normalized_bucket(cls, status: str, *, is_blocking: bool = False) -> str:
        normalized = str(status or "").strip().lower()
        if is_blocking and normalized not in {"closed", "resolved", "cancelled", "void"}:
            return "blocking"
        if normalized == "open":
            return "awaiting_site"
        if normalized == "answered":
            return "awaiting_review"
        if normalized in {"resolved", "closed"}:
            return normalized
        return "all"

    @staticmethod
    def _filter_contexts_for_search(contexts, search: str):
        needle = str(search or "").strip().lower()
        if not needle:
            return contexts, ""
        matched = {}
        for page_state_id, context in contexts.items():
            haystack = " ".join(
                (
                    context.subject_code,
                    context.screening_code,
                    getattr(context, "randomization_code", ""),
                    context.event_code,
                    context.event_label,
                    context.crf_page_label,
                )
            ).lower()
            if needle in haystack:
                matched[page_state_id] = context
        if matched:
            return matched, ""
        return contexts, search

    def _to_query_item(
        self,
        row: dict[str, object],
        contexts,
        *,
        user_display_by_id: dict[int, str],
    ) -> QueryListItemDTO:
        context = contexts.get(int(row["page_state_id"]))
        page_state_label = f"Page State #{row['page_state_id']}"
        field_path = str(row.get("field_path") or "").strip()
        field_label = str(row.get("field_label") or "").strip()
        subject_code = getattr(context, "subject_code", "") or ""
        screening_code = getattr(context, "screening_code", "") or ""
        detail_study_id = getattr(context, "study_id", None) or 0
        detail_url = reverse(
            "reconcile:query_detail",
            kwargs={"study_id": detail_study_id, "query_id": row["query_id"]},
        )
        review_focus_url = self._review_focus_url(context)
        return QueryListItemDTO(
            query_id=row["query_id"],
            study_id=getattr(context, "study_id", None),
            site_id=getattr(context, "site_id", None),
            subject_id=getattr(context, "subject_id", None),
            status=str(row.get("status") or ""),
            normalized_bucket=self.normalized_bucket(
                str(row.get("status") or ""),
                is_blocking=bool(row.get("is_blocking")),
            ),
            pending_with=self.pending_with(str(row.get("status") or "")),
            source=str(row.get("source") or ""),
            query_type=str(row.get("query_type") or ""),
            severity=str(row.get("severity") or ""),
            is_blocking=bool(row.get("is_blocking")),
            question_text_excerpt=Truncator(str(row.get("question_text") or "")).chars(140),
            resolution_note=str(row.get("resolution_note") or ""),
            field_path=field_path,
            value_snapshot_excerpt=Truncator(str(row.get("value_snapshot") or "")).chars(80),
            opened_at=row.get("opened_at"),
            answered_at=row.get("answered_at"),
            resolved_at=row.get("resolved_at"),
            closed_at=row.get("closed_at"),
            last_activity_at=row.get("last_activity_at"),
            reply_count=int(row.get("reply_count") or 0),
            assigned_to_display=self._user_display(row.get("assigned_to_id"), user_display_by_id),
            opened_by_display=self._user_display(row.get("opened_by_id"), user_display_by_id),
            subject_code=subject_code or "—",
            screening_code=screening_code or "—",
            subject_display_code=subject_code or screening_code or "—",
            event_code=getattr(context, "event_code", "") or "",
            event_label=getattr(context, "event_label", "") or f"Event #{getattr(context, 'event_instance_id', '')}",
            crf_page_label=getattr(context, "crf_page_label", "") or page_state_label,
            field_label_or_path=field_label or (f"Field: {field_path}" if field_path else "—"),
            review_focus_url=review_focus_url,
            page_state_label=page_state_label,
            detail_url=detail_url,
        )

    @staticmethod
    def _review_focus_url(context) -> str:
        if context is None:
            return ""
        study_id = getattr(context, "study_id", None)
        subject_id = getattr(context, "subject_id", None)
        event_instance_id = getattr(context, "event_instance_id", None)
        form_id = getattr(context, "event_form_binding_id", None) or getattr(
            context,
            "page_template_id",
            None,
        )
        if not (study_id and subject_id and event_instance_id and form_id):
            return ""
        detail_url = reverse(
            "subject:subject_detail",
            kwargs={"study_id": study_id, "subject_id": subject_id},
        )
        return f"{detail_url}?mode=verification&event={event_instance_id}&form={form_id}"

    def _to_validation_issue_item(
        self,
        row: dict[str, object],
        contexts,
        *,
        user_display_by_id: dict[int, str],
    ) -> ValidationIssueListItemDTO:
        context = contexts.get(int(row["page_state_id"]))
        return ValidationIssueListItemDTO(
            issue_id=row["issue_id"],
            study_id=getattr(context, "study_id", None),
            site_id=getattr(context, "site_id", None),
            subject_id=getattr(context, "subject_id", None),
            page_state_id=int(row["page_state_id"]),
            status=str(row.get("status") or ""),
            severity=str(row.get("severity") or ""),
            message=str(row.get("message") or ""),
            failed_value=row.get("failed_value"),
            created_at=row.get("created_at"),
            resolved_at=row.get("resolved_at"),
            acknowledged_at=row.get("acknowledged_at"),
            acknowledged_by_display=self._user_display(
                row.get("acknowledged_by_id"),
                user_display_by_id,
            ),
            subject_code=getattr(context, "subject_code", "") or "—",
            screening_code=getattr(context, "screening_code", "") or "—",
            event_label=getattr(context, "event_label", "") or f"Event #{getattr(context, 'event_instance_id', '')}",
            crf_page_label=getattr(context, "crf_page_label", "") or f"Page State #{row['page_state_id']}",
            field_label=str(row.get("field_label") or ""),
            review_focus_url=self._review_focus_url(context),
            page_state_label=f"Page State #{row['page_state_id']}",
        )

    @staticmethod
    def _row_user_ids(rows) -> set:
        user_ids = set()
        for row in rows or ():
            user_ids.add(row.get("assigned_to_id"))
            user_ids.add(row.get("opened_by_id"))
        return user_ids

    @staticmethod
    def _user_display_map(user_ids) -> dict[int, str]:
        normalized_ids = {int(user_id) for user_id in user_ids or () if user_id not in (None, "")}
        if not normalized_ids:
            return {}
        from apps.identity.public import get_user_display_map

        return get_user_display_map(normalized_ids)

    @staticmethod
    def _user_display(user_id, user_display_by_id: dict[int, str]) -> str:
        if user_id in (None, ""):
            return "—"
        normalized_id = int(user_id)
        return user_display_by_id.get(normalized_id) or f"User #{normalized_id}"


__all__ = [
    "QUERY_WORKBENCH_BUCKETS",
    "QueryListItemDTO",
    "QueryThreadDTO",
    "ValidationIssueListItemDTO",
    "QueryWorkbenchReader",
    "QueryWorkbenchResultDTO",
    "QueryWorkbenchSummaryDTO",
]
