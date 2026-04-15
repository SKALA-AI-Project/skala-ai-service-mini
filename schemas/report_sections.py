from __future__ import annotations

from typing import TypedDict


class ReportSections(TypedDict):
    """피드백 반영 후 최종 보고서 섹션 구조를 고정한다."""

    executive_summary: str
    analysis_background: str
    tech_status: str
    investigation_results: str
    conclusion: str
    reference: str
