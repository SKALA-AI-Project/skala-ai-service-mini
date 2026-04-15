from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

from schemas.state import WorkflowState

if TYPE_CHECKING:
    from config import RuntimeConfig


@dataclass
class ValidationResult:
    """설계 요구사항과 현재 결과의 매핑 검증 결과를 담는다."""

    passed: bool
    missing_items: list[str]


class SupervisorAgent:
    """단계 실행 순서와 품질 검증을 중앙에서 통제한다."""

    required_sections = [
        "executive_summary",
        "analysis_background",
        "investigation_results",
        "strategic_implications",
        "conclusion",
        "reference",
    ]

    default_topics = ["HBM4", "PIM", "CXL"]
    default_competitors = ["Samsung", "Micron"]

    def extract_request_scope(
        self,
        user_query: str,
        default_date_range: dict[str, str],
    ) -> tuple[list[str], list[str], dict[str, str], str]:
        """사용자 쿼리에서 분석 범위를 추출하고, 없으면 기본값을 유지한다."""
        normalized = user_query.lower()

        detected_topics: list[str] = []
        topic_aliases = {
            "HBM4": ("hbm4",),
            "PIM": ("pim", "processing in memory"),
            "CXL": ("cxl",),
        }
        for topic, aliases in topic_aliases.items():
            if any(alias in normalized for alias in aliases):
                detected_topics.append(topic)

        detected_competitors: list[str] = []
        competitor_aliases = {
            "Samsung": ("samsung", "삼성", "삼성전자"),
            "Micron": ("micron", "마이크론"),
        }
        for competitor, aliases in competitor_aliases.items():
            if any(alias in normalized for alias in aliases):
                detected_competitors.append(competitor)

        topics = detected_topics or self.default_topics.copy()
        competitors = detected_competitors or self.default_competitors.copy()
        date_range = self._extract_date_range(user_query, default_date_range)
        scope_source = "query" if detected_topics or detected_competitors or date_range != default_date_range else "default"
        return topics, competitors, date_range, scope_source

    def _extract_date_range(
        self,
        user_query: str,
        default_date_range: dict[str, str],
    ) -> dict[str, str]:
        """간단한 한국어 기간 표현에서 개월 수를 추출한다."""
        match = re.search(r"최근\s*(\d+)\s*개월", user_query)
        if not match:
            return default_date_range

        from datetime import date, timedelta

        months = int(match.group(1))
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        return {"from": start_date.isoformat(), "to": end_date.isoformat()}

    def generate_report_title(
        self,
        user_query: str,
        topics: list[str],
        competitors: list[str],
        config: "RuntimeConfig | None" = None,
    ) -> str:
        """gpt-4o-mini를 활용해 분석 목적에 맞는 보고서 제목을 생성한다.
        mock 모드(use_live_api=False)이거나 config가 없으면 기본 제목을 반환한다.
        """
        tech_str = " · ".join(topics)
        if config is None or not config.use_live_api:
            return f"{tech_str} 기반 기술 경쟁력 보고서"

        from openai import OpenAI

        client = OpenAI(api_key=config.openai_api_key)
        prompt = (
            "다음 조건으로 반도체 기술 분석 보고서 제목을 한국어로 한 줄 생성하세요.\n"
            f"분석 기술: {', '.join(topics)}\n"
            f"사용자 요청: {user_query or '없음'}\n\n"
            "조건:\n"
            f"- 형식: '{tech_str} 기반 {{분석 유형}} 보고서'\n"
            "- 25자 이내의 간결한 제목\n"
            "- SK하이닉스 R&D 전략 보고서 톤\n"
            "- 반드시 '보고서'로 끝낼 것\n"
            "- 제목 텍스트만 출력 (따옴표·부제목 없음)"
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.1,
        )
        title = response.choices[0].message.content.strip().strip("\"'「」『』")
        return title or f"{tech_str} 기반 기술 경쟁력 보고서"

    def validate_search_coverage(self, state: WorkflowState) -> ValidationResult:
        """모든 기술과 경쟁사가 검색 결과에 포함됐는지 확인한다.
        기술별 최소 수집 건수(3건)도 함께 검증한다.
        """
        pairs = {(item["tech"], item["company"]) for item in state["search_results"]}
        missing_items: list[str] = []

        for tech in state["topics"]:
            for company in state["competitors"]:
                if (tech, company) not in pairs:
                    missing_items.append(f"검색 누락: {tech} / {company}")

        # 기술별 최소 수집 건수 검증 (기술당 최소 3건)
        for tech in state["topics"]:
            tech_count = sum(1 for item in state["search_results"] if item["tech"] == tech)
            if tech_count < 3:
                missing_items.append(f"기술별 최소 수집 미달: {tech} ({tech_count}건 < 3건)")

        return ValidationResult(passed=not missing_items, missing_items=missing_items)

    def validate_trl_coverage(self, state: WorkflowState) -> ValidationResult:
        """TRL 평가가 기술·기업 조합별로 모두 생성됐는지 확인한다."""
        missing_items: list[str] = []

        for tech in state["topics"]:
            assessments = state["trl_assessment"].get(tech, {})
            for company in state["competitors"]:
                if company not in assessments:
                    missing_items.append(f"TRL 누락: {tech} / {company}")

        return ValidationResult(passed=not missing_items, missing_items=missing_items)

    def validate_draft(self, state: WorkflowState) -> ValidationResult:
        """보고서 초안이 7개 섹션을 모두 채웠는지 검증한다."""
        missing_items = [
            f"섹션 누락: {section}"
            for section in self.required_sections
            if not state["draft_content"].get(section, "").strip()
        ]
        return ValidationResult(passed=not missing_items, missing_items=missing_items)

    def validate_design_mapping(self, state: WorkflowState) -> ValidationResult:
        """design.md의 핵심 요구사항과 구현 결과를 1:1로 대조한다.
        최신성(최근 90일 자료 비율)과 참고문헌 URL 수도 검증한다.
        """
        from datetime import date, timedelta

        missing_items: list[str] = []

        scope_source = str(state["metadata"].get("scope_source", "default"))
        if scope_source == "default":
            if len(set(state["topics"])) != 3:
                missing_items.append("설계 불일치: 3개 기술 기본 범위 미충족")
            if set(state["competitors"]) != {"Samsung", "Micron"}:
                missing_items.append("설계 불일치: 경쟁사 기본 범위 미충족")
        else:
            if not state["topics"]:
                missing_items.append("설계 불일치: 사용자 쿼리 기반 기술 범위 추출 실패")
            if not state["competitors"]:
                missing_items.append("설계 불일치: 사용자 쿼리 기반 경쟁사 범위 추출 실패")

        if not state["bias_check"] and state["hitl_approved"] is not True:
            missing_items.append("설계 불일치: 편향 검증 또는 HITL 승인 미충족")

        use_live_api = str(state["metadata"].get("USE_LIVE_API", "False")) == "True"
        if not state["final_report_md_path"]:
            missing_items.append("설계 불일치: Markdown 산출물 미생성")
        if use_live_api and not state["final_report_pdf_path"]:
            missing_items.append("설계 불일치: PDF 산출물 미생성")

        quality_scores = state["quality_scores"]
        required_quality_keys = {
            "search_richness",
            "bias_score",
            "summary_score",
            "coverage_score",
            "evidence_score",
            "consistency_score",
        }
        if not required_quality_keys.issubset(set(quality_scores)):
            missing_items.append("설계 불일치: 품질 점수 일부 누락")

        # 최신성 검증: 최근 90일 이내 자료가 전체의 50% 이상이어야 한다
        search_results = state.get("search_results", [])
        if search_results:
            cutoff = (date.today() - timedelta(days=90)).isoformat()
            recent_count = sum(
                1 for item in search_results
                if item.get("published_date", "") >= cutoff
            )
            total = len(search_results)
            if recent_count / total < 0.5:
                missing_items.append(
                    f"최신성 미달: 최근 90일 자료 비율 {recent_count}/{total} (50% 미만)"
                )

        # 참고문헌 URL 수 검증: 검색결과 수의 1/3 이상이어야 한다
        reference_text = state.get("draft_content", {}).get("reference", "")
        url_count = reference_text.count("http")
        min_urls = max(3, len(search_results) // 3) if search_results else 3
        if url_count < min_urls:
            missing_items.append(
                f"참고문헌 URL 부족: {url_count}개 (최소 {min_urls}개 필요)"
            )

        # 챕터별 경쟁사·기술 키워드 커버리지 검증
        final_md = state.get("final_report_md", "")
        if final_md:
            missing_items.extend(
                self._validate_section_coverage(
                    final_md,
                    topics=state["topics"],
                    competitors=state["competitors"],
                )
            )

        return ValidationResult(passed=not missing_items, missing_items=missing_items)

    # ------------------------------------------------------------------
    # 섹션별 커버리지 헬퍼
    # ------------------------------------------------------------------

    def _parse_markdown_sections(self, markdown: str) -> dict[str, str]:
        """Markdown을 H1 헤딩 기준으로 섹션별 본문을 반환한다.
        섹션 제목에서 번호 접두사(예: '1. ')를 제거하여 키로 사용한다.
        """
        sections: dict[str, str] = {}
        current_title: str | None = None
        current_lines: list[str] = []

        for line in markdown.splitlines():
            if line.startswith("# "):
                if current_title is not None:
                    sections[current_title] = "\n".join(current_lines)
                raw = line[2:].strip()
                title = re.sub(r"^\d+\.\s+", "", raw)
                current_title = title
                current_lines = []
            elif current_title is not None:
                current_lines.append(line)

        if current_title is not None:
            sections[current_title] = "\n".join(current_lines)
        return sections

    def _validate_section_coverage(
        self,
        markdown: str,
        topics: list[str],
        competitors: list[str],
    ) -> list[str]:
        """각 주요 챕터에 경쟁사와 기술 키워드가 균등하게 포함됐는지 검증한다."""
        missing: list[str] = []
        sections = self._parse_markdown_sections(markdown)

        # 경쟁사·기술을 모두 균등하게 포함해야 하는 챕터
        chapters_requiring_balance = [
            "EXECUTIVE SUMMARY",
            "분석 배경 및 기술 현황",
            "전략적 시사점",
            "결론",
        ]

        for chapter in chapters_requiring_balance:
            content = sections.get(chapter, "").lower()
            if not content:
                continue

            for competitor in competitors:
                if competitor.lower() not in content:
                    missing.append(
                        f"커버리지 미달: '{chapter}' 챕터에 {competitor} 미언급"
                    )

            for topic in topics:
                if topic.lower() not in content:
                    missing.append(
                        f"커버리지 미달: '{chapter}' 챕터에 {topic} 미언급"
                    )

        # 조사 결과 챕터: 각 경쟁사 소섹션 존재 여부
        investigation = sections.get("조사 결과", "")
        for competitor in competitors:
            if competitor not in investigation:
                missing.append(
                    f"커버리지 미달: '조사 결과' 챕터에 {competitor} 소섹션 누락"
                )

        return missing
