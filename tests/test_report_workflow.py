import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from workflows.report_workflow import run_report_workflow


class ReportWorkflowTest(unittest.TestCase):
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
            self.assertIn("## 1.1 분석 목적", report_text)
            self.assertIn("# 3. 조사 결과", report_text)
            self.assertIn("## 3.1.1 Micron 동향", report_text)
            self.assertIn("## 3.2.1 Samsung 동향", report_text)
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


if __name__ == "__main__":
    unittest.main()
