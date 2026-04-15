from __future__ import annotations

from typing import TypedDict


class ReportSections(TypedDict):
    """피드백 반영 후 최종 보고서 섹션 구조를 고정한다."""

    executive_summary: str
    analysis_background: str  # 분석 배경 및 기술 현황 통합
    investigation_results: str
    strategic_implications: str  # 전략적 시사점 (별도 챕터)
    conclusion: str
    reference: str
