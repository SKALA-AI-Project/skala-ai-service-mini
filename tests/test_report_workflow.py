from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from workflows.report_workflow import run_report_workflow, build_initial_state


class ReportWorkflowE2ETest(unittest.TestCase):
    """모의 데이터 기반 E2E 흐름을 검증한다."""

    def test_report_workflow_runs_end_to_end(self) -> None:
        with TemporaryDirectory() as temp_dir:
            state = run_report_workflow(output_dir=Path(temp_dir), use_live_api=False)

            self.assertTrue(state["hitl_approved"] is True or state["bias_check"])
            self.assertTrue(Path(state["final_report_md_path"]).exists())
            self.assertEqual(state["final_report_pdf_path"], "")
            self.assertIn("summary_score", state["quality_scores"])
            self.assertIn("HBM4", state["trl_assessment"])

            report_text = Path(state["final_report_md_path"]).read_text(encoding="utf-8")
            self.assertIn("# EXECUTIVE SUMMARY", report_text)
            self.assertIn("# 1. 분석 배경", report_text)
            self.assertIn("# 3. 조사 결과", report_text)
            self.assertIn("# 4. 결론", report_text)

    def test_supervisor_can_override_default_scope_from_query(self) -> None:
        with TemporaryDirectory() as temp_dir:
            state = run_report_workflow(
                output_dir=Path(temp_dir),
                user_query="최근 6개월 기준으로 HBM4와 PIM만 Samsung 중심으로 분석해줘",
                use_live_api=False,
            )

            self.assertEqual(state["topics"], ["HBM4", "PIM"])
            self.assertEqual(state["competitors"], ["Samsung"])
            self.assertEqual(state["metadata"]["scope_source"], "query")
            self.assertNotIn("Micron", state["final_report_md"])
            self.assertNotIn("CXL", state["final_report_md"])
            self.assertIn("## 3.1 Samsung", state["final_report_md"])
            self.assertIn("## 3.1.2 Samsung TRL 기반 기술 성숙도", state["final_report_md"])


class ReportWorkflowQualityScoresTest(unittest.TestCase):
    """품질 점수가 설계 문서의 6개 키를 모두 포함하는지 검증한다."""

    def test_all_quality_score_keys_present(self) -> None:
        with TemporaryDirectory() as temp_dir:
            state = run_report_workflow(output_dir=Path(temp_dir), use_live_api=False)

        required_keys = {
            "search_richness", "bias_score",
            "summary_score", "coverage_score", "evidence_score", "consistency_score",
        }
        self.assertTrue(required_keys.issubset(set(state["quality_scores"].keys())))


class ReportWorkflowFormattingFailureTest(unittest.TestCase):
    """PDF 생성 실패 시 Markdown 보존과 error_log 기록을 검증한다."""

    def test_markdown_preserved_when_pdf_skipped(self) -> None:
        """mock 모드에서는 PDF 없이 Markdown만 생성되어야 한다."""
        with TemporaryDirectory() as temp_dir:
            state = run_report_workflow(output_dir=Path(temp_dir), use_live_api=False)
            # mock 모드에서 PDF 경로는 비어있어야 한다
            self.assertEqual(state["final_report_pdf_path"], "")
            # Markdown은 반드시 존재해야 한다
            self.assertTrue(Path(state["final_report_md_path"]).exists())

    def test_formatting_failure_logged_in_error_log(self) -> None:
        """PDF 생성 실패(mock 경로)가 error_log에 기록되는지 확인한다."""
        with TemporaryDirectory() as temp_dir:
            state = run_report_workflow(output_dir=Path(temp_dir), use_live_api=False)
        # mock 경로에서는 PDF 실패 로그가 error_log에 남는다
        has_formatting_error = any("포맷팅" in msg for msg in state["error_log"])
        self.assertTrue(has_formatting_error)


class ReportWorkflowSectionCoverageTest(unittest.TestCase):
    """최종 보고서가 7개 섹션을 모두 포함하는지 검증한다."""

    def test_all_seven_sections_present(self) -> None:
        with TemporaryDirectory() as temp_dir:
            state = run_report_workflow(output_dir=Path(temp_dir), use_live_api=False)
            report = Path(state["final_report_md_path"]).read_text(encoding="utf-8")
            expected_headings = [
                "# EXECUTIVE SUMMARY",
                "# 1. 분석 배경",
                "# 2. 기술 현황",
                "# 3. 조사 결과",
                "# 4. 결론",
                "# REFERENCE",
            ]
            for heading in expected_headings:
                self.assertIn(heading, report, msg=f"섹션 누락: {heading}")

    def test_trl_disclaimer_inserted_when_estimated_present(self) -> None:
        """추정 TRL이 있으면 면책 문구가 보고서에 삽입되어야 한다."""
        with TemporaryDirectory() as temp_dir:
            state = run_report_workflow(output_dir=Path(temp_dir), use_live_api=False)
            report = Path(state["final_report_md_path"]).read_text(encoding="utf-8")
            # mock 데이터에는 "추정"이 포함되므로 면책 문구가 삽입되어야 한다
            if "추정" in report:
                self.assertIn("TRL 4~6", report)


class ReportWorkflowHitlTriggerTest(unittest.TestCase):
    """HITL 트리거 조건과 warning_flag 설정을 검증한다."""

    def test_initial_state_has_hitl_not_triggered(self) -> None:
        """초기 상태에서 hitl_approved는 None이어야 한다."""
        state = build_initial_state(use_live_api=False)
        self.assertIsNone(state["hitl_approved"])

    def test_warning_flag_false_by_default(self) -> None:
        """초기 상태에서 warning_flag는 False여야 한다."""
        state = build_initial_state(use_live_api=False)
        self.assertFalse(state["warning_flag"])

    def test_mock_mode_passes_bias_check(self) -> None:
        """mock 모드에서 bias_check가 통과되어 HITL이 트리거되지 않아야 한다."""
        with TemporaryDirectory() as temp_dir:
            state = run_report_workflow(output_dir=Path(temp_dir), use_live_api=False)

        # mock 모드에서는 bias_check가 통과되므로 HITL 불필요
        self.assertTrue(state["bias_check"])
        self.assertFalse(state["warning_flag"])


class ReportWorkflowDesignValidationTest(unittest.TestCase):
    """설계-구현 1:1 검증 루프가 올바르게 동작하는지 확인한다."""

    def test_design_validation_log_created(self) -> None:
        """설계 검증 로그 파일이 생성되어야 한다."""
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "reports"
            run_report_workflow(output_dir=output_dir, use_live_api=False)
            log_file = output_dir.parent / "logs" / "design_validation.md"
            self.assertTrue(log_file.exists())

    def test_draft_retry_count_not_double_incremented(self) -> None:
        """설계 검증 루프가 draft_retry_count를 중복 증가시키지 않아야 한다."""
        with TemporaryDirectory() as temp_dir:
            state = run_report_workflow(output_dir=Path(temp_dir), use_live_api=False)

        # 설계 검증 루프는 별도 카운터(design_retry)를 사용하므로
        # draft_retry_count는 초안 루프에서의 값만 반영해야 한다
        self.assertLessEqual(state["draft_retry_count"], 2)

    def test_trl_assessment_all_pairs_present(self) -> None:
        """TRL 평가가 모든 기술·기업 조합에 대해 생성되어야 한다."""
        with TemporaryDirectory() as temp_dir:
            state = run_report_workflow(output_dir=Path(temp_dir), use_live_api=False)

        for tech in state["topics"]:
            for company in state["competitors"]:
                self.assertIn(tech, state["trl_assessment"])
                self.assertIn(company, state["trl_assessment"][tech])


if __name__ == "__main__":
    unittest.main()
