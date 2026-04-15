from __future__ import annotations
from collections import defaultdict
from textwrap import dedent

from langchain_core.prompts import ChatPromptTemplate
from langsmith import traceable
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from config import RuntimeConfig
from schemas.report_sections import ReportSections
from schemas.search_result import SearchResult
from schemas.trl_assessment import TrlAssessment


class DraftSectionsOutput(BaseModel):
    """LLM이 반환해야 하는 7개 보고서 섹션 구조다."""

    summary: str = Field(description="핵심 내용을 요약한 SUMMARY")
    background: str = Field(description="분석 배경")
    tech_status: str = Field(description="기술 현황")
    competitor: str = Field(description="경쟁사 비교")
    trl_assessment: str = Field(description="TRL 평가와 해석")
    insight: str = Field(description="전략적 시사점")
    reference: str = Field(description="URL 기반 참고문헌 목록")


class DraftScoreOutput(BaseModel):
    """초안 품질 평가 결과다."""

    summary_score: int = Field(ge=1, le=5)
    coverage_score: int = Field(ge=1, le=5)
    evidence_score: int = Field(ge=1, le=5)
    consistency_score: int = Field(ge=1, le=5)


class DraftGenerationAgent:
    """검색 결과와 TRL 평가를 바탕으로 7개 섹션 초안을 생성한다."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.llm = (
            ChatOpenAI(
                api_key=config.openai_api_key,
                model=config.openai_model,
                temperature=0.2,
            )
            if config.openai_api_key
            else None
        )

    @traceable(name="draft_generate", run_type="chain")
    def generate(
        self,
        search_results: list[SearchResult],
        assessments: dict[str, dict[str, TrlAssessment]],
    ) -> tuple[ReportSections, dict[str, int], str]:
        """보고서 섹션, 품질 점수, 전체 Markdown 문자열을 반환한다."""
        if self.config.use_live_api and self.llm:
            return self._generate_with_llm(search_results, assessments)
        return self._generate_with_rules(search_results, assessments)

    def _generate_with_llm(
        self,
        search_results: list[SearchResult],
        assessments: dict[str, dict[str, TrlAssessment]],
    ) -> tuple[ReportSections, dict[str, int], str]:
        """최신 LangChain + OpenAI 구조화 출력을 사용해 초안을 생성한다."""
        assert self.llm is not None

        evidence_lines = []
        for item in search_results[:24]:
            evidence_lines.append(
                f"- 기술={item['tech']} / 기업={item['company']} / 관점={item['perspective']} "
                f"/ 출처유형={item['source_type']} / 제목={item['title']} / "
                f"URL={item['url']} / 내용={item['content'][:700]}"
            )

        trl_lines = []
        for tech, company_map in assessments.items():
            for company, assessment in company_map.items():
                trl_lines.append(
                    f"- {tech} / {company}: TRL={assessment['trl']}, "
                    f"basis={assessment['basis']}, confidence={assessment['confidence']}, "
                    f"evidence={'; '.join(assessment['evidence'])}, "
                    f"limitation={assessment['limitation']}"
                )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    dedent(
                        """
                        너는 SK하이닉스 R&D 전략 담당자를 위한 기술 전략 분석 보고서를 작성하는 분석가다.
                        반드시 한국어로 작성하고, 보수적이고 검증 가능한 표현을 사용한다.
                        basis=estimated 인 항목은 반드시 "추정"과 한계를 드러내라.
                        """
                    ).strip(),
                ),
                (
                    "human",
                    dedent(
                        """
                        아래 근거를 바탕으로 7개 섹션을 모두 작성하라.

                        제약:
                        - HBM4, PIM, CXL 3개 기술을 모두 포함한다.
                        - Samsung, Micron 비교를 포함한다.
                        - reference는 URL bullet list로 작성한다.

                        검색 근거:
                        {evidence_block}

                        TRL 근거:
                        {trl_block}
                        """
                    ).strip(),
                ),
            ]
        )

        chain = prompt | self.llm.with_structured_output(DraftSectionsOutput)
        llm_sections = chain.invoke(
            {
                "evidence_block": "\n".join(evidence_lines),
                "trl_block": "\n".join(trl_lines),
            }
        )
        sections = ReportSections(
            summary=llm_sections.summary,
            background=llm_sections.background,
            tech_status=llm_sections.tech_status,
            competitor=llm_sections.competitor,
            trl_assessment=llm_sections.trl_assessment,
            insight=llm_sections.insight,
            reference=llm_sections.reference,
        )
        markdown = self._to_markdown(sections)
        scores = self._score_with_llm(markdown)
        return sections, scores, markdown

    def _generate_with_rules(
        self,
        search_results: list[SearchResult],
        assessments: dict[str, dict[str, TrlAssessment]],
    ) -> tuple[ReportSections, dict[str, int], str]:
        """API 사용이 어려운 환경을 위한 규칙 기반 대체 경로다."""
        references = "\n".join(
            f"- {item['tech']} / {item['company']}: {item['url']}" for item in search_results
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
        scores = self._score_with_rules(sections, search_results)
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

    def _score_with_llm(self, markdown: str) -> dict[str, int]:
        """LLM으로 초안 품질을 재평가한다."""
        assert self.llm is not None

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "너는 기술 보고서 품질 평가자다. 반드시 JSON 스키마에 맞게만 응답한다.",
                ),
                (
                    "human",
                    dedent(
                        """
                        아래 보고서를 1~5점으로 평가하라.

                        평가 항목:
                        - summary_score: 요약의 핵심성
                        - coverage_score: 7개 섹션 완결도
                        - evidence_score: URL 근거와 주장 연결성
                        - consistency_score: 섹션 간 논리 일관성

                        보고서:
                        {markdown}
                        """
                    ).strip(),
                ),
            ]
        )
        chain = prompt | self.llm.with_structured_output(DraftScoreOutput)
        scores = chain.invoke({"markdown": markdown[:12000]})
        return {
            "summary_score": scores.summary_score,
            "coverage_score": scores.coverage_score,
            "evidence_score": scores.evidence_score,
            "consistency_score": scores.consistency_score,
        }

    def _score_with_rules(
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
