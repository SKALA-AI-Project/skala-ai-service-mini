from __future__ import annotations

from collections import defaultdict

from schemas.report_sections import ReportSections
from schemas.search_result import SearchResult
from schemas.trl_assessment import TrlAssessment


class DraftGenerationAgent:
    """검색 결과와 TRL 평가를 바탕으로 7개 섹션 초안을 생성한다."""

    sections = [
        "summary",
        "background",
        "tech_status",
        "competitor",
        "trl_assessment",
        "insight",
        "reference",
    ]

    def generate(
        self,
        search_results: list[SearchResult],
        assessments: dict[str, dict[str, TrlAssessment]],
    ) -> tuple[ReportSections, dict[str, int], str]:
        """보고서 섹션, 품질 점수, 전체 Markdown 문자열을 반환한다."""
        references = "\n".join(
            f"- {item['tech']} / {item['company']}: {item['url']}"
            for item in search_results
        )

        grouped = defaultdict(list)
        for item in search_results:
            grouped[item["tech"]].append(item["company"])

        summary = (
            "본 보고서는 HBM4, PIM, CXL을 대상으로 삼성전자와 마이크론의 최근 "
            "기술 동향과 TRL 성숙도를 비교해 전략적 시사점을 정리한다."
        )
        background = (
            "AI 인프라 확대에 따라 고성능 메모리 기술 경쟁이 심화되고 있으며, "
            "HBM4, PIM, CXL은 차세대 AI 시스템 성능을 좌우하는 핵심 축이다."
        )
        tech_status = "\n".join(
            f"- {tech}: 최근 검색 결과 기준 {len(companies)}개 경쟁사 관점 자료 확보"
            for tech, companies in grouped.items()
        )
        competitor = "\n".join(
            [
                "- Samsung: 공개 발표 범위는 넓지만 일부 항목은 보수적으로 해석해야 함",
                "- Micron: 제품 로드맵과 시장 관점 자료가 비교적 명확하게 관찰됨",
            ]
        )

        trl_lines: list[str] = []
        for tech, company_map in assessments.items():
            for company, assessment in company_map.items():
                basis_text = "확인" if assessment["basis"] == "confirmed" else "추정"
                limitation = (
                    f" / 한계: {assessment['limitation']}"
                    if assessment["limitation"]
                    else ""
                )
                trl_lines.append(
                    f"- {tech} / {company}: TRL {assessment['trl']} ({basis_text}, "
                    f"confidence={assessment['confidence']}){limitation}"
                )

        insight = "\n".join(
            [
                "- HBM4는 비교적 높은 성숙도 구간으로, 공급 경쟁과 수율 확보가 핵심이다.",
                "- PIM은 상용화 판단에 보수적 접근이 필요하며, 간접지표 기반 추정이 많다.",
                "- CXL은 표준 확산과 데이터센터 채택 속도를 함께 봐야 한다.",
            ]
        )

        sections = ReportSections(
            summary=summary,
            background=background,
            tech_status=tech_status,
            competitor=competitor,
            trl_assessment="\n".join(trl_lines),
            insight=insight,
            reference=references,
        )
        markdown = self._to_markdown(sections)
        scores = self._score(sections, search_results)
        return sections, scores, markdown

    def _to_markdown(self, sections: ReportSections) -> str:
        """7개 섹션을 최종 Markdown 초안 형태로 직렬화한다."""
        return "\n\n".join(
            [
                "# SUMMARY\n" + sections["summary"],
                "# 1. Background\n" + sections["background"],
                "# 2. Tech Status\n" + sections["tech_status"],
                "# 3. Competitor\n" + sections["competitor"],
                "# 4. TRL Assessment\n" + sections["trl_assessment"],
                "# 5. Insight\n" + sections["insight"],
                "# REFERENCE\n" + sections["reference"],
            ]
        )

    def _score(
        self,
        sections: ReportSections,
        search_results: list[SearchResult],
    ) -> dict[str, int]:
        """설계 문서의 초안 품질 항목을 단순 규칙으로 평가한다."""
        coverage_score = 5 if all(sections.values()) else 2
        summary_score = 5 if len(sections["summary"]) >= 40 else 3
        evidence_score = 5 if len(search_results) >= 6 else 2
        consistency_score = 5 if "TRL" in sections["trl_assessment"] else 2
        return {
            "summary_score": summary_score,
            "coverage_score": coverage_score,
            "evidence_score": evidence_score,
            "consistency_score": consistency_score,
        }
