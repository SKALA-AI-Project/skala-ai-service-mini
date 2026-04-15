from __future__ import annotations

from typing import Any, TypedDict

from schemas.report_sections import ReportSections
from schemas.search_result import SearchResult
from schemas.trl_assessment import TrlAssessment


class WorkflowState(TypedDict):
    """설계 문서의 상태 정의를 코드로 고정한 shared state다."""

    topics: list[str]
    competitors: list[str]
    date_range: dict[str, str]
    retry_count: int
    bias_retry_count: int
    draft_retry_count: int
    error_log: list[str]
    search_results: list[SearchResult]
    bias_check: bool
    hitl_approved: bool | None
    warning_flag: bool
    trl_assessment: dict[str, dict[str, TrlAssessment]]
    draft_content: ReportSections
    quality_scores: dict[str, int]
    final_report_md: str
    final_report_md_path: str
    final_report_pdf_path: str
    metadata: dict[str, Any]
