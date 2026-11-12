import json
from dataclasses import dataclass
from typing import Any

from apps.core.form_data_document import flatten_form_data_for_export, normalize_form_data
from apps.datacapture.infrastructure.repositories import DjangoDataCapturePageRepository


@dataclass(frozen=True)
class PageStateContextDTO:
    page_state_id: int
    study_id: int | None
    site_id: int | None
    subject_id: int | None
    subject_code: str
    screening_code: str
    randomization_code: str
    event_instance_id: int | None
    event_code: str
    event_label: str
    crf_page_label: str
    page_template_id: int | None
    event_form_binding_id: int | None


class DataCapturePageStateReadService:

    def __init__(self, repository=None):
        self.repository = repository or DjangoDataCapturePageRepository()

    def get_page_state_status(
        self,
        *,
        subject_id: int,
        visit_id: int,
        crf_template_id: int,
        event_form_binding_id: int | None = None,
    ) -> str:
        page_state = self.repository.get_page_state_by_scope(
            subject_id=subject_id,
            visit_id=visit_id,
            crf_template_id=crf_template_id,
            event_form_binding_id=event_form_binding_id,
        )
        if page_state is None:
            return ""
        return (page_state.status or "").strip()

    def get_page_state_id_for_scope(
        self,
        *,
        subject_id: int,
        visit_id: int,
        crf_template_id: int,
        event_form_binding_id: int | None = None,
    ) -> int | None:
        page_state = self.repository.get_page_state_by_scope(
            subject_id=subject_id,
            visit_id=visit_id,
            crf_template_id=crf_template_id,
            event_form_binding_id=event_form_binding_id,
        )
        if page_state is None:
            return None
        return int(page_state.id)

    def get_latest_stable_page_state_id_for_event_instance(self, *, event_instance_id: int) -> int | None:
        return self.repository.get_latest_stable_page_state_id_for_event_instance(
            event_instance_id=event_instance_id,
        )

    def get_latest_submitted_or_stable_page_state_id_for_event_instance(self, *, event_instance_id: int) -> int | None:
        return self.repository.get_latest_submitted_or_stable_page_state_id_for_event_instance(
            event_instance_id=event_instance_id,
        )

    def event_instance_has_data(self, *, event_instance_id: int) -> bool:
        return self.repository.event_instance_has_data(event_instance_id=event_instance_id)

    def get_page_state_final_data_map(
        self,
        *,
        subject_id: int,
        visit_id: int,
        crf_template_id: int,
        event_form_binding_id: int | None = None,
    ) -> dict[str, Any]:
        page_state = self.repository.get_page_state_by_scope(
            subject_id=subject_id,
            visit_id=visit_id,
            crf_template_id=crf_template_id,
            event_form_binding_id=event_form_binding_id,
        )
        if page_state is None or not (page_state.final_data or "").strip():
            return {}
        try:
            parsed = json.loads(page_state.final_data)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        doc = normalize_form_data(parsed, strict=False)
        return {
            k: v
            for k, v in flatten_form_data_for_export(doc, repeat_strategy="legacy_repeat_suffix").items()
            if k != "__form_verification__"
        }

    def get_page_state_contexts(self, *, page_state_ids: list[int] | tuple[int, ...]) -> dict[int, PageStateContextDTO]:
        rows = self.repository.list_page_state_contexts(page_state_ids=tuple(page_state_ids or ()))
        return self._to_context_dto_map(rows)

    def list_page_state_contexts_for_study_site(
        self,
        *,
        study_id: int,
        site_id: int | None = None,
    ) -> dict[int, PageStateContextDTO]:
        rows = self.repository.list_page_state_contexts(study_id=study_id, site_id=site_id)
        return self._to_context_dto_map(rows)

    @staticmethod
    def _to_context_dto_map(rows) -> dict[int, PageStateContextDTO]:
        contexts: dict[int, PageStateContextDTO] = {}
        for row in rows:
            page_state_id = int(row["page_state_id"])
            contexts[page_state_id] = PageStateContextDTO(
                page_state_id=page_state_id,
                study_id=row["study_id"],
                site_id=row["site_id"],
                subject_id=row["subject_id"],
                subject_code=row["subject_code"],
                screening_code=row["screening_code"],
                randomization_code=row.get("randomization_code") or "",
                event_instance_id=row["event_instance_id"],
                event_code=row["event_code"],
                event_label=row["event_label"],
                crf_page_label=row["crf_page_label"],
                page_template_id=row["page_template_id"],
                event_form_binding_id=row.get("event_form_binding_id"),
            )
        return contexts
