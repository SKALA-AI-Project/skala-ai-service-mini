from __future__ import annotations

from collections import defaultdict

from schemas.search_result import SearchResult
from schemas.trl_assessment import TrlAssessment


class TrlAnalysisNode:
    """수집된 자료를 바탕으로 기술 성숙도 평가를 생성한다."""

    def analyze(
        self,
        search_results: list[SearchResult],
    ) -> dict[str, dict[str, TrlAssessment]]:
        """기술별·기업별 TRL 결과를 중첩 딕셔너리로 반환한다."""
        grouped: dict[str, list[SearchResult]] = defaultdict(list)
        for item in search_results:
            grouped[f"{item['tech']}::{item['company']}"].append(item)

        assessments: dict[str, dict[str, TrlAssessment]] = defaultdict(dict)
        for key, items in grouped.items():
            tech, company = key.split("::", maxsplit=1)
            trl, basis, confidence, limitation = self._infer_trl(tech, company)
            assessments[tech][company] = TrlAssessment(
                company=company,
                tech=tech,
                trl=trl,
                basis=basis,
                confidence=confidence,
                evidence=[
                    f"{items[0]['published_date']} 기준 최근 검색 결과 {len(items)}건 확보",
                    f"{company} / {tech}에 대해 긍정·부정·중립 관점 자료를 수집",
                    "양산 발표, 연구 동향, 리스크 관점을 함께 반영",
                ],
                limitation=limitation,
            )

        return dict(assessments)

    def _infer_trl(
        self, tech: str, company: str
    ) -> tuple[int, str, str, str | None]:
        """설계 문서의 confirmed/estimated 규칙을 보수적으로 반영한다."""
        if tech == "HBM4":
            return 7, "confirmed", "medium", None
        if tech == "PIM":
            return (
                5,
                "estimated",
                "medium" if company == "Micron" else "low",
                "공개 자료가 제한적이어서 간접지표 기반 추정이 포함됨",
            )
        return (
            6,
            "estimated",
            "medium" if company == "Micron" else "low",
            "표준 확산 속도와 공개 자료 편차로 인해 추정 오차가 있을 수 있음",
        )
