from __future__ import annotations

from typing import TypedDict


class ReportSections(TypedDict):
    """최종 보고서 7개 섹션 구조를 고정한다."""

    summary: str
    background: str
    tech_status: str
    competitor: str
    trl_assessment: str
    insight: str
    reference: str
