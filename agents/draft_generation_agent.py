from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langsmith import traceable

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from config import RuntimeConfig
from prompts.draft_prompt import DRAFT_SYSTEM_PROMPT, DRAFT_USER_PROMPT_TEMPLATE
from prompts.quality_prompt import QUALITY_SYSTEM_PROMPT, QUALITY_USER_PROMPT_TEMPLATE
from schemas.report_sections import ReportSections
from schemas.search_result import SearchResult
from schemas.trl_assessment import TrlAssessment


class DraftSectionsOutput(BaseModel):
    """LLM이 반환해야 하는 보고서 섹션 구조.
    각 섹션의 분량 요건은 프롬프트(DRAFT_USER_PROMPT_TEMPLATE)에서 주입된다.
    """

    executive_summary: str = Field(description="EXECUTIVE SUMMARY 본문")
    analysis_background: str = Field(description="분석 배경 본문 (목적·범위 통합)")
    tech_status: str = Field(description="기술 현황 본문")
    investigation_results: str = Field(description="경쟁사별 조사 결과 본문")
    conclusion: str = Field(description="결론 본문")
    reference: str = Field(description="URL 기반 참고문헌 목록")


class DraftScoreOutput(BaseModel):
    """초안 품질 평가 결과다."""

    summary_score: int = Field(ge=1, le=5)
    coverage_score: int = Field(ge=1, le=5)
    evidence_score: int = Field(ge=1, le=5)
    consistency_score: int = Field(ge=1, le=5)


class DraftGenerationAgent:
    """검색 결과와 TRL 평가를 바탕으로 보고서 초안을 생성한다."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        # DraftConfig 에서 길이 기준 읽기
        self._exec_sum_min: int = config.draft.executive_summary_min
        self._exec_sum_max: int = config.draft.executive_summary_max
        self._section_min: int = config.draft.section_min_length
        self.draft_llm = (
            ChatOpenAI(
                api_key=config.openai_api_key,
                model=config.draft_model,
                temperature=0.2,
            )
            if config.openai_api_key
            else None
        )
        self.judge_llm = (
            ChatOpenAI(
                api_key=config.openai_api_key,
                model=config.judge_model,
                temperature=0.0,
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
        print(
            "[LOG] 초안 생성 시작:"
            f" search_results={len(search_results)},"
            f" assessment_techs={list(assessments.keys())}"
        )
        if self.config.use_live_api and self.draft_llm and self.judge_llm:
            print(
                "[LOG] DraftGenerationAgent LLM 경로 사용:"
                f" draft_model={self.config.draft_model},"
                f" judge_model={self.config.judge_model}"
            )
            return self._generate_with_llm(search_results, assessments)
        print("[LOG] DraftGenerationAgent 규칙 기반 경로 사용")
        return self._generate_with_rules(search_results, assessments)

    def _generate_with_llm(
        self,
        search_results: list[SearchResult],
        assessments: dict[str, dict[str, TrlAssessment]],
    ) -> tuple[ReportSections, dict[str, int], str]:
        """최신 LangChain + OpenAI 구조화 출력을 사용해 초안을 생성한다."""
        assert self.draft_llm is not None

        topics = list(assessments.keys())
        competitors = sorted(
            {
                company
                for company_map in assessments.values()
                for company in company_map.keys()
            }
        )

        evidence_lines = []
        for item in search_results:
            evidence_lines.append(
                f"- 기술={item['tech']} / 기업={item['company']} / 관점={item['perspective']} "
                f"/ 출처유형={item['source_type']} / 제목={item['title']} / "
                f"URL={item['url']} / 내용={item['content'][:1200]}"
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
                ("system", DRAFT_SYSTEM_PROMPT),
                ("human", DRAFT_USER_PROMPT_TEMPLATE),
            ]
        )

        competitor_sections_spec = self._build_competitor_sections_spec(competitors)

        chain = prompt | self.draft_llm.with_structured_output(DraftSectionsOutput)
        llm_sections = chain.invoke(
            {
                "topic_scope": ", ".join(topics),
                "competitor_scope": ", ".join(competitors),
                "evidence_block": "\n".join(evidence_lines),
                "trl_block": "\n".join(trl_lines),
                "exec_sum_min": self._exec_sum_min,
                "exec_sum_max": self._exec_sum_max,
                "section_min": self._section_min,
                "competitor_sections_spec": competitor_sections_spec,
            }
        )
        sections = ReportSections(
            executive_summary=llm_sections.executive_summary,
            analysis_background=llm_sections.analysis_background,
            tech_status=llm_sections.tech_status,
            investigation_results=llm_sections.investigation_results,
            conclusion=llm_sections.conclusion,
            reference=llm_sections.reference,
        )
        markdown = self._to_markdown(sections)
        markdown = self._enforce_scope(markdown, topics, competitors)
        scores = self._score_with_llm(markdown)
        print(f"[LOG] LLM 초안 생성 완료: draft_scores={scores}")
        return sections, scores, markdown

    def _generate_with_rules(
        self,
        search_results: list[SearchResult],
        assessments: dict[str, dict[str, TrlAssessment]],
    ) -> tuple[ReportSections, dict[str, int], str]:
        """테스트·오프라인 환경용 최소 구조 스켈레톤을 반환한다.
        실제 내용 생성은 _generate_with_llm(gpt-4o)이 담당한다."""
        topics = list(assessments.keys())
        competitors = sorted(
            {
                company
                for company_map in assessments.values()
                for company in company_map.keys()
            }
        )

        result_blocks: list[str] = []
        for index, competitor in enumerate(competitors, start=1):
            trl_lines = [
                f"{topic}: TRL {assessments[topic][competitor]['trl']} ({assessments[topic][competitor]['basis']})"
                for topic in topics
                if competitor in assessments.get(topic, {})
            ]
            result_blocks.append(
                f"## 3.{index} {competitor}\n\n"
                f"### 3.{index}.1 {competitor} 동향\n{competitor} 동향 (mock).\n\n"
                f"### 3.{index}.2 {competitor} TRL 기반 기술 성숙도\n"
                + "\n".join(trl_lines) + "\n\n"
                + f"### 3.{index}.3 {competitor} 전략적 시사점\n{competitor} 전략적 시사점 (mock)."
            )

        sections = ReportSections(
            executive_summary=f"{', '.join(topics)} 기술 대상 {', '.join(competitors)} 분석 요약 (mock).",
            analysis_background=f"분석 기술: {', '.join(topics)} / 경쟁사: {', '.join(competitors)} (mock).",
            tech_status=f"{', '.join(topics)} 기술 현황 요약 (mock).",
            investigation_results="\n\n".join(result_blocks),
            conclusion=f"{', '.join(topics)} 기반 SK하이닉스 대응 방향 요약 (mock).",
            reference="\n".join(
                f"- [{item['title']}]({item['url']})" for item in search_results
            ),
        )
        markdown = self._to_markdown(sections)
        scores = self._score_with_rules(sections, search_results)
        print(f"[LOG] 스켈레톤 초안 생성 완료(mock): draft_scores={scores}")
        return sections, scores, markdown

    def _to_markdown(self, sections: ReportSections) -> str:
        """피드백에서 요구한 목차 구조로 Markdown을 직렬화한다."""
        return "\n\n".join(
            [
                "# EXECUTIVE SUMMARY\n" + sections["executive_summary"],
                "# 1. 분석 배경\n" + sections["analysis_background"],
                "# 2. 기술 현황\n" + sections["tech_status"],
                "# 3. 조사 결과\n" + sections["investigation_results"],
                "# 4. 결론\n" + sections["conclusion"],
                "# REFERENCE\n" + sections["reference"],
            ]
        )

    def _score_with_llm(self, markdown: str) -> dict[str, int]:
        """LLM으로 초안 품질을 재평가한다."""
        assert self.judge_llm is not None

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", QUALITY_SYSTEM_PROMPT),
                ("human", QUALITY_USER_PROMPT_TEMPLATE),
            ]
        )
        chain = prompt | self.judge_llm.with_structured_output(DraftScoreOutput)
        scores = chain.invoke({"markdown": markdown[:15000]})
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
        """규칙 기반 품질 점수를 계산한다."""
        coverage_score = 5 if all(sections.values()) else 2
        summary_score = (
            5
            if self._exec_sum_min <= len(sections["executive_summary"]) <= self._exec_sum_max
            else 3
        )
        evidence_score = 5 if len(search_results) >= 6 else 2
        consistency_score = 5 if "TRL" in sections["investigation_results"] else 2
        return {
            "summary_score": summary_score,
            "coverage_score": coverage_score,
            "evidence_score": evidence_score,
            "consistency_score": consistency_score,
        }

    def _build_competitor_sections_spec(self, competitors: list[str]) -> str:
        """LLM 프롬프트에 주입할 경쟁사별 섹션 목차 명세를 동적으로 생성한다."""
        lines: list[str] = []
        for i, competitor in enumerate(competitors, start=1):
            lines += [
                f"- ## 3.{i} {competitor}",
                f"- ### 3.{i}.1 {competitor} 동향: 최소 {self._section_min}자",
                f"- ### 3.{i}.2 {competitor} TRL 기반 기술 성숙도: 최소 {self._section_min}자",
                f"- ### 3.{i}.3 {competitor} 전략적 시사점: 최소 {self._section_min}자",
            ]
        return "\n".join(lines)

    def _enforce_scope(
        self,
        markdown: str,
        topics: list[str],
        competitors: list[str],
    ) -> str:
        """LLM 출력에서 요청 범위를 벗어난 기술 토픽만 필터링한다.
        경쟁사는 동적으로 결정되므로 하드코딩하지 않는다.
        """
        # 프로젝트에서 다루는 전체 기술 목록 중 요청에 없는 것만 금지
        all_known_topics = ["HBM4", "PIM", "CXL"]
        forbidden_tokens = [t for t in all_known_topics if t not in topics]

        if not forbidden_tokens:
            return markdown

        filtered_lines: list[str] = []
        for line in markdown.splitlines():
            if any(token in line for token in forbidden_tokens):
                continue
            filtered_lines.append(line)
        return "\n".join(filtered_lines)
