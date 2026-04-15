from __future__ import annotations

from typing import Literal, TypedDict


class TrlAssessment(TypedDict):
    """기술·기업별 TRL 평가 결과를 정의한다."""

    company: str
    tech: str
    trl: int
    basis: Literal["confirmed", "estimated"]
    confidence: Literal["high", "medium", "low"]
    evidence: list[str]
    limitation: str | None
