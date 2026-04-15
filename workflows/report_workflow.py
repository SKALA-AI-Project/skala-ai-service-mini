from __future__ import annotations

import os
from pathlib import Path

from agents.draft_generation_agent import DraftGenerationAgent
from agents.formatting_node import FormattingNode
from agents.hitl_node import HitlNode
from agents.supervisor import SupervisorAgent
from agents.trl_analysis_node import TrlAnalysisNode
from agents.web_search_agent import WebSearchAgent
from config import RuntimeConfig, load_runtime_config
from schemas.state import WorkflowState


def load_runtime_metadata(use_live_api: bool) -> dict[str, str]:
    """`.env.example`의 키가 현재 런타임에 반영됐는지 요약한다."""
    config = load_runtime_config(use_live_api=use_live_api)
    return {
        "OPENAI_API_KEY_SET": str(bool(config.openai_api_key)),
        "LANGCHAIN_API_KEY_SET": str(bool(config.langchain_api_key)),
        "LANGCHAIN_TRACING_V2": config.langchain_tracing_v2,
        "LANGCHAIN_ENDPOINT": config.langchain_endpoint,
        "LANGCHAIN_PROJECT": config.langchain_project,
        "HUGGINGFACEHUB_API_TOKEN_SET": str(bool(config.huggingfacehub_api_token)),
        "TAVILY_API_KEY_SET": str(bool(config.tavily_api_key)),
        "OPENAI_MODEL": config.openai_model,
        "USE_LIVE_API": str(config.use_live_api),
    }


def build_initial_state(use_live_api: bool = True) -> WorkflowState:
    """설계 문서 기준의 초기 상태를 생성한다."""
    config = load_runtime_config(use_live_api=use_live_api)
    search_agent = WebSearchAgent(config)
    return WorkflowState(
        topics=["HBM4", "PIM", "CXL"],
        competitors=["Samsung", "Micron"],
        date_range=search_agent.build_date_range(),
        retry_count=0,
        bias_retry_count=0,
        draft_retry_count=0,
        error_log=[],
        search_results=[],
        bias_check=False,
        hitl_approved=None,
        warning_flag=False,
        trl_assessment={},
        draft_content={
            "summary": "",
            "background": "",
            "tech_status": "",
            "competitor": "",
            "trl_assessment": "",
            "insight": "",
            "reference": "",
        },
        quality_scores={},
        final_report_md="",
        final_report_md_path="",
        final_report_pdf_path="",
        metadata=load_runtime_metadata(use_live_api=use_live_api),
    )


def run_report_workflow(output_dir: Path, use_live_api: bool = True) -> WorkflowState:
    """Supervisor 중심 순차 실행 워크플로우를 수행한다."""
    config = load_runtime_config(use_live_api=use_live_api)
    _apply_langsmith_environment(config)

    state = build_initial_state(use_live_api=use_live_api)
    supervisor = SupervisorAgent()
    search_agent = WebSearchAgent(config)
    trl_node = TrlAnalysisNode()
    draft_agent = DraftGenerationAgent(config)
    formatting_node = FormattingNode()
    hitl_node = HitlNode()

    # 검색 단계는 편향 검증과 커버리지 검증을 함께 통과할 때까지 재시도한다.
    while state["bias_retry_count"] <= 2:
        search_results, search_scores, bias_check = search_agent.collect(
            topics=state["topics"],
            competitors=state["competitors"],
            date_range=state["date_range"],
        )
        state["search_results"] = search_results
        state["quality_scores"].update(search_scores)
        state["bias_check"] = bias_check

        search_validation = supervisor.validate_search_coverage(state)
        if search_validation.passed and state["bias_check"]:
            break

        state["bias_retry_count"] += 1
        state["error_log"].extend(search_validation.missing_items)

        if state["bias_retry_count"] > 2:
            state["hitl_approved"] = hitl_node.review(state)
            state["warning_flag"] = True
            break

    state["trl_assessment"] = trl_node.analyze(state["search_results"])
    trl_validation = supervisor.validate_trl_coverage(state)
    if not trl_validation.passed:
        state["error_log"].extend(trl_validation.missing_items)

    # 초안 단계는 필수 섹션과 최소 품질 점수를 만족할 때까지 재생성한다.
    while state["draft_retry_count"] <= 2:
        sections, draft_scores, markdown = draft_agent.generate(
            state["search_results"],
            state["trl_assessment"],
        )
        state["draft_content"] = sections
        state["quality_scores"].update(draft_scores)
        state["final_report_md"] = markdown

        draft_validation = supervisor.validate_draft(state)
        if draft_validation.passed and _draft_scores_pass(state["quality_scores"]):
            break

        state["draft_retry_count"] += 1
        state["error_log"].extend(draft_validation.missing_items)

    md_path, pdf_path = formatting_node.export(markdown, output_dir)
    state["final_report_md_path"] = md_path
    state["final_report_pdf_path"] = pdf_path

    # 최종 단계에서는 design.md 핵심 요구사항과 실제 산출물을 1:1로 대조한다.
    while state["retry_count"] <= 2:
        design_validation = supervisor.validate_design_mapping(state)
        _write_design_validation_log(output_dir, design_validation)
        if design_validation.passed:
            break

        state["retry_count"] += 1
        state["error_log"].extend(design_validation.missing_items)
        state["draft_retry_count"] += 1
        sections, draft_scores, markdown = draft_agent.generate(
            state["search_results"],
            state["trl_assessment"],
        )
        state["draft_content"] = sections
        state["quality_scores"].update(draft_scores)
        state["final_report_md"] = markdown
        md_path, pdf_path = formatting_node.export(markdown, output_dir)
        state["final_report_md_path"] = md_path
        state["final_report_pdf_path"] = pdf_path

    return state


def _apply_langsmith_environment(config: RuntimeConfig) -> None:
    """LangSmith 추적에 필요한 환경 변수를 프로세스에 주입한다."""
    os.environ["LANGCHAIN_TRACING_V2"] = config.langchain_tracing_v2
    os.environ["LANGCHAIN_ENDPOINT"] = config.langchain_endpoint
    os.environ["LANGCHAIN_PROJECT"] = config.langchain_project
    if config.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = config.langchain_api_key


def _draft_scores_pass(quality_scores: dict[str, int]) -> bool:
    """설계 문서의 최소 품질 기준을 코드로 표현한다."""
    return all(
        quality_scores.get(key, 0) >= 3
        for key in [
            "summary_score",
            "coverage_score",
            "evidence_score",
            "consistency_score",
        ]
    )


def _write_design_validation_log(output_dir: Path, validation: object) -> None:
    """설계-구현 1:1 검증 결과를 로그 파일로 남긴다."""
    logs_dir = output_dir.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    passed = getattr(validation, "passed", False)
    missing_items = getattr(validation, "missing_items", [])
    log_lines = ["# 설계 검증 결과", "", f"- 통과 여부: {passed}"]
    if missing_items:
        log_lines.append("- 누락 항목:")
        log_lines.extend([f"  - {item}" for item in missing_items])
    else:
        log_lines.append("- 누락 항목: 없음")

    (logs_dir / "design_validation.md").write_text(
        "\n".join(log_lines),
        encoding="utf-8",
    )
