from __future__ import annotations

from dataclasses import dataclass
import re

from schemas.state import WorkflowState


@dataclass
class ValidationResult:
    """설계 요구사항과 현재 결과의 매핑 검증 결과를 담는다."""

    passed: bool
    missing_items: list[str]


class SupervisorAgent:
    """단계 실행 순서와 품질 검증을 중앙에서 통제한다."""

    required_sections = [
        "executive_summary",
        "analysis_purpose",
        "analysis_scope",
        "tech_status",
        "investigation_results",
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

    def validate_search_coverage(self, state: WorkflowState) -> ValidationResult:
        """모든 기술과 경쟁사가 검색 결과에 포함됐는지 확인한다."""
        pairs = {(item["tech"], item["company"]) for item in state["search_results"]}
        missing_items: list[str] = []

        for tech in state["topics"]:
            for company in state["competitors"]:
                if (tech, company) not in pairs:
                    missing_items.append(f"검색 누락: {tech} / {company}")

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
        """design.md의 핵심 요구사항과 구현 결과를 1:1로 대조한다."""
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

        return ValidationResult(passed=not missing_items, missing_items=missing_items)
