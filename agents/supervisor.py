from __future__ import annotations

from dataclasses import dataclass

from schemas.state import WorkflowState


@dataclass
class ValidationResult:
    """설계 요구사항과 현재 결과의 매핑 검증 결과를 담는다."""

    passed: bool
    missing_items: list[str]


class SupervisorAgent:
    """단계 실행 순서와 품질 검증을 중앙에서 통제한다."""

    required_sections = [
        "summary",
        "background",
        "tech_status",
        "competitor",
        "trl_assessment",
        "insight",
        "reference",
    ]

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

        if len(set(state["topics"])) != 3:
            missing_items.append("설계 불일치: 3개 기술 범위 미충족")

        if set(state["competitors"]) != {"Samsung", "Micron"}:
            missing_items.append("설계 불일치: 경쟁사 범위 미충족")

        if not state["bias_check"] and state["hitl_approved"] is not True:
            missing_items.append("설계 불일치: 편향 검증 또는 HITL 승인 미충족")

        if not state["final_report_md_path"] or not state["final_report_pdf_path"]:
            missing_items.append("설계 불일치: Markdown/PDF 산출물 미생성")

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
