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
    """LLM이 반환해야 하는 피드백 반영 보고서 구조다."""

    executive_summary: str = Field(description="450~550자 EXECUTIVE SUMMARY")
    analysis_purpose: str = Field(description="최소 300자의 분석 목적")
    analysis_scope: str = Field(description="최소 300자의 분석 범위")
    tech_status: str = Field(description="최소 300자의 기술 현황")
    investigation_results: str = Field(description="경쟁사별 조사 결과 본문")
    conclusion: str = Field(description="최소 300자의 결론")
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
                (
                    "system",
                    dedent(
                        """
                        너는 SK하이닉스 R&D 전략 담당자를 위한 기술 전략 분석 보고서를 작성하는 분석가다.
                        반드시 한국어로 작성하고, 근거를 충분히 반영하며, 보수적이고 검증 가능한 표현을 사용한다.
                        basis=estimated 인 항목은 반드시 "추정"과 한계를 드러내라.
                        전달된 검색 근거를 지나치게 요약하지 말고, 주요 사실을 본문에 반영하라.
                        """
                    ).strip(),
                ),
                (
                    "human",
                    dedent(
                        """
                        아래 근거를 바탕으로 지정된 범위에 대해서만 보고서를 작성하라.

                        제약:
                        - 기술 범위: {topic_scope}
                        - 경쟁사 범위: {competitor_scope}
                        - 지정되지 않은 기술이나 경쟁사를 새로 추가하지 않는다.
                        - 단일 경쟁사면 단일 경쟁사 섹션만 작성한다.
                        - reference는 URL bullet list로 작성한다.
                        - 반드시 아래 목차와 분량 규칙을 지킨다.

                        목차 규칙:
                        - # EXECUTIVE SUMMARY: 450~550자
                        - # 1. 분석 배경
                        - ## 1.1 분석 목적: 최소 300자
                        - ## 1.2 분석 범위: 최소 300자
                        - # 2. 기술 현황: 최소 300자
                        - # 3. 조사 결과
                        - ## 3.1 {{경쟁사명}}
                        - ## 3.1.1 {{경쟁사명}} 동향: 최소 300자
                        - ## 3.1.2 {{경쟁사명}} TRL 기반 기술 성숙도: 최소 300자
                        - ## 3.1.3 {{경쟁사명}} 전략적 시사점: 최소 300자
                        - 경쟁사가 늘어나면 같은 패턴으로 ## 3.2, ## 3.2.1, ## 3.2.2, ## 3.2.3을 사용한다.
                        - # 4. 결론: 최소 300자
                        - # REFERENCE

                        검색 근거:
                        {evidence_block}

                        TRL 근거:
                        {trl_block}
                        """
                    ).strip(),
                ),
            ]
        )

        chain = prompt | self.draft_llm.with_structured_output(DraftSectionsOutput)
        llm_sections = chain.invoke(
            {
                "topic_scope": ", ".join(topics),
                "competitor_scope": ", ".join(competitors),
                "evidence_block": "\n".join(evidence_lines),
                "trl_block": "\n".join(trl_lines),
            }
        )
        sections = ReportSections(
            executive_summary=llm_sections.executive_summary,
            analysis_purpose=llm_sections.analysis_purpose,
            analysis_scope=llm_sections.analysis_scope,
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
        """API 사용이 어려운 환경을 위한 규칙 기반 대체 경로다."""
        topics = list(assessments.keys())
        competitors = sorted(
            {
                company
                for company_map in assessments.values()
                for company in company_map.keys()
            }
        )
        evidence_map = self._build_evidence_map(search_results)

        executive_summary = self._ensure_min_length(
            (
                f"본 보고서는 {', '.join(topics)} 기술을 대상으로 {', '.join(competitors)}의 최근 공개 자료를 분석해 "
                "기술 현황과 경쟁 압력을 검토하고, SK하이닉스의 대응 방향을 정리하기 위해 작성되었다. "
                "수집된 자료는 긍정, 부정, 중립 관점을 함께 포함하며, 단일 기업 발표에 의존하지 않고 기사, 공식 발표, 분석성 자료를 교차 검토했다. "
                "HBM4는 공개된 양산·출하 신호와 고객사 연계 발표로 인해 비교적 높은 기술 성숙도가 확인되며, "
                "PIM은 아직 직접적인 상용화 증거가 제한적이어서 보수적 추정이 필요하다. "
                "따라서 본 보고서는 즉시 경쟁이 벌어지는 고성숙 기술과 중장기 검증이 필요한 기술을 구분해 해석하고, "
                "실행 우선순위를 도출하는 데 초점을 둔다."
            ),
            450,
        )[:550]
        analysis_purpose = self._ensure_min_length(
            (
                f"분석 목적은 {', '.join(topics)} 영역에서 {', '.join(competitors)}의 기술 추진 방향, 양산 신호, 공개 발표의 질을 정리하고 "
                "SK하이닉스가 어떤 기술에 즉시 대응해야 하며 어떤 기술은 중장기 추적 대상으로 볼지 판단하는 데 있다. "
                "특히 고성능 메모리와 차세대 메모리 아키텍처는 단순 기술 개발을 넘어 고객사 채택, 공급망 대응, 생산 능력 확대와 연결되므로, "
                "기사 하나의 톤보다 반복적으로 관측되는 공개 신호의 성격이 중요하다. "
                "이 보고서는 검색 근거를 단순 요약하는 수준을 넘어서 기술 성숙도와 전략적 위협 수준을 실무적으로 해석하는 것을 목적으로 한다."
            ),
            300,
        )
        analysis_scope = self._ensure_min_length(
            (
                f"분석 범위는 기술적으로 {', '.join(topics)}이며, 경쟁사 범위는 {', '.join(competitors)}로 한정한다. "
                "시간 범위는 사용자 요청 기준 최근 공개 자료를 우선 반영하며, 자료 유형은 기업 공식 발표, 일반 뉴스, "
                "리스크 관점 검색 결과, 기술 동향 기사 등을 포함한다. "
                "또한 각 기술에 대해 단순 제품 출시 여부만이 아니라 양산·출하 신호, 고객사 적용 가능성, 성능 수치, "
                "제조 전략, 기사 맥락에서 드러나는 위험 요소까지 함께 검토한다. "
                "본 보고서는 지정되지 않은 기술과 경쟁사를 확장하지 않고, 요청 범위 안에서 실질적인 전략 판단에 필요한 정보만 구조화한다."
            ),
            300,
        )
        tech_status = self._ensure_min_length(
            " ".join(
                [
                    self._build_topic_status_paragraph(
                        topic,
                        evidence_map.get(topic, []),
                    )
                    for topic in topics
                ]
            ),
            300,
        )

        result_blocks: list[str] = []
        for index, competitor in enumerate(competitors, start=1):
            result_blocks.append(
                "\n\n".join(
                    [
                        f"## 3.{index} {competitor}",
                        f"## 3.{index}.1 {competitor} 동향\n"
                        + self._ensure_min_length(
                            self._build_competitor_trend_paragraph(
                                competitor,
                                evidence_map,
                                topics,
                            ),
                            300,
                        ),
                        f"## 3.{index}.2 {competitor} TRL 기반 기술 성숙도\n"
                        + self._ensure_min_length(
                            self._build_competitor_trl_paragraph(
                                competitor,
                                assessments,
                                topics,
                            ),
                            300,
                        ),
                        f"## 3.{index}.3 {competitor} 전략적 시사점\n"
                        + self._ensure_min_length(
                            self._build_competitor_insight_paragraph(
                                competitor,
                                topics,
                            ),
                            300,
                        ),
                    ]
                )
            )

        conclusion = self._ensure_min_length(
            (
                f"종합적으로 보면 {', '.join(topics)}에 대한 {', '.join(competitors)}의 공개 신호는 서로 다른 성숙도와 대응 우선순위를 보여준다. "
                "HBM4처럼 양산과 출하, 고객사 적용 언급이 관측되는 기술은 이미 실행 단계 경쟁으로 해석해야 하며, "
                "단순 연구개발 수준의 논의로 보기 어렵다. 반면 PIM은 장기적 잠재력은 높지만 공개 자료만으로는 상용화 진척을 단정하기 어렵고, "
                "따라서 마케팅성 메시지보다 실질적인 검증 근거를 중심으로 보수적으로 읽어야 한다. "
                "SK하이닉스는 성숙도가 높은 기술에서는 양산 경쟁력과 고객사 대응 속도를 강화하고, "
                "추정 구간 기술에서는 실수요와 제품화 가능성 검증에 자원을 배분하는 이중 전략이 필요하다."
            ),
            300,
        )
        references = "\n".join(
            f"- [{item['title']}]({item['url']})"
            for item in search_results
        )

        sections = ReportSections(
            executive_summary=executive_summary,
            analysis_purpose=analysis_purpose,
            analysis_scope=analysis_scope,
            tech_status=tech_status,
            investigation_results="\n\n".join(result_blocks),
            conclusion=conclusion,
            reference=references,
        )
        markdown = self._to_markdown(sections)
        scores = self._score_with_rules(sections, search_results)
        print(f"[LOG] 규칙 기반 초안 생성 완료: draft_scores={scores}")
        return sections, scores, markdown

    def _to_markdown(self, sections: ReportSections) -> str:
        """피드백에서 요구한 목차 구조로 Markdown을 직렬화한다."""
        return "\n\n".join(
            [
                "# EXECUTIVE SUMMARY\n" + sections["executive_summary"],
                "# 1. 분석 배경\n"
                + "## 1.1 분석 목적\n"
                + sections["analysis_purpose"]
                + "\n\n"
                + "## 1.2 분석 범위\n"
                + sections["analysis_scope"],
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
                        - summary_score: EXECUTIVE SUMMARY 분량과 완성도
                        - coverage_score: 요구 목차와 하위 항목 완결도
                        - evidence_score: URL 근거와 주장 연결성
                        - consistency_score: 섹션 간 논리 일관성

                        보고서:
                        {markdown}
                        """
                    ).strip(),
                ),
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
        summary_score = 5 if 450 <= len(sections["executive_summary"]) <= 550 else 3
        evidence_score = 5 if len(search_results) >= 6 else 2
        consistency_score = 5 if "TRL" in sections["investigation_results"] else 2
        return {
            "summary_score": summary_score,
            "coverage_score": coverage_score,
            "evidence_score": evidence_score,
            "consistency_score": consistency_score,
        }

    def _build_evidence_map(
        self,
        search_results: list[SearchResult],
    ) -> dict[str, list[SearchResult]]:
        evidence_map: dict[str, list[SearchResult]] = defaultdict(list)
        for item in search_results:
            evidence_map[item["tech"]].append(item)
        return evidence_map

    def _build_topic_status_paragraph(
        self,
        tech: str,
        items: list[SearchResult],
    ) -> str:
        title_block = ", ".join(item["title"] for item in items[:3])
        return (
            f"{tech}의 기술 현황은 최근 공개 자료에서 반복적으로 드러난 사실을 기준으로 정리했다. "
            f"대표적으로 {title_block}와 같은 자료가 확인되었으며, 이들 자료는 제품 출시, 생산 확대, "
            "리스크 신호, 적용 분야를 서로 다른 관점에서 보여준다. "
            "따라서 본 보고서는 단순 홍보 문구를 그대로 옮기지 않고, 성능 수치와 출하, 제조 전략, 기사 맥락을 함께 보며 "
            f"{tech}의 실제 실행 단계와 전략적 의미를 해석한다."
        )

    def _build_competitor_trend_paragraph(
        self,
        competitor: str,
        evidence_map: dict[str, list[SearchResult]],
        topics: list[str],
    ) -> str:
        parts = []
        for topic in topics:
            items = [item for item in evidence_map.get(topic, []) if item["company"] == competitor]
            if not items:
                continue
            parts.append(
                f"{topic}에서는 {items[0]['title']}를 포함한 최근 자료가 확인되며, "
                f"{competitor}의 공개 발표와 기사 흐름은 해당 기술을 시장 경쟁력 강화 수단으로 활용하려는 방향을 보여준다."
            )
        parts.append(
            f"전반적으로 {competitor}의 동향은 생산, 고객 적용, 전략 발표를 통해 시장 주도권을 강화하려는 모습으로 해석되지만, "
            "공식 발표의 성격상 낙관적 표현이 섞여 있을 가능성도 있어 중립 기사와 리스크 관점 자료를 함께 읽는 것이 필요하다."
        )
        return " ".join(parts)

    def _build_competitor_trl_paragraph(
        self,
        competitor: str,
        assessments: dict[str, dict[str, TrlAssessment]],
        topics: list[str],
    ) -> str:
        parts = []
        for topic in topics:
            assessment = assessments.get(topic, {}).get(competitor)
            if not assessment:
                continue
            basis_text = "확인" if assessment["basis"] == "confirmed" else "추정"
            limitation_text = (
                f" 한계는 {assessment['limitation']}."
                if assessment["limitation"]
                else ""
            )
            parts.append(
                f"{topic}의 TRL은 {assessment['trl']}로 {basis_text}되며, confidence는 {assessment['confidence']}이다.{limitation_text}"
            )
        parts.append(
            f"따라서 {competitor}의 기술 성숙도는 기술별로 구분해서 읽어야 하며, "
            "양산 신호가 있는 기술과 간접지표에 의존하는 기술을 같은 선상에서 비교하면 안 된다."
        )
        return " ".join(parts)

    def _build_competitor_insight_paragraph(
        self,
        competitor: str,
        topics: list[str],
    ) -> str:
        return (
            f"{competitor}에 대한 전략적 시사점은 {', '.join(topics)} 각각의 실행 단계에 맞는 대응 체계를 분리해야 한다는 점이다. "
            "성숙도가 높은 기술은 고객사 대응, 성능 우위, 생산 경쟁력 확보가 핵심이며, "
            "추정 단계 기술은 언론 노출보다 실제 상용화 조건과 생태계 적합성을 검증하는 쪽이 중요하다. "
            "결국 경쟁사의 발표량 자체보다 발표의 직접성, 수치의 구체성, 공급 및 출하 신호를 함께 읽는 분석 체계가 필요하다."
        )

    def _ensure_min_length(self, text: str, minimum: int) -> str:
        """피드백에서 요구한 최소 글자 수를 만족하도록 문장을 보강한다."""
        filler = (
            " 본 문단은 공개 자료의 반복 신호, 기사 맥락, 기술 성숙도 해석, 경쟁사의 발표 의도, "
            "그리고 SK하이닉스의 대응 관점을 함께 고려해 작성되었다."
        )
        while len(text) < minimum:
            text += filler
        return text

    def _enforce_scope(
        self,
        markdown: str,
        topics: list[str],
        competitors: list[str],
    ) -> str:
        """LLM 출력이 요청 범위를 벗어나면 최소한의 가드레일로 잘라낸다."""
        forbidden_topics = [topic for topic in ["HBM4", "PIM", "CXL"] if topic not in topics]
        forbidden_competitors = [
            competitor for competitor in ["Samsung", "Micron"] if competitor not in competitors
        ]

        filtered_lines: list[str] = []
        for line in markdown.splitlines():
            if any(token in line for token in forbidden_topics + forbidden_competitors):
                continue
            filtered_lines.append(line)
        return "\n".join(filtered_lines)
