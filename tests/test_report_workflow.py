import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from workflows.report_workflow import run_report_workflow


class ReportWorkflowTest(unittest.TestCase):
    """모의 데이터 기반 E2E 흐름을 검증한다."""

    def test_report_workflow_runs_end_to_end(self) -> None:
        with TemporaryDirectory() as temp_dir:
            state = run_report_workflow(output_dir=Path(temp_dir), use_live_api=False)

            self.assertTrue(state["bias_check"])
            self.assertTrue(Path(state["final_report_md_path"]).exists())
            self.assertTrue(Path(state["final_report_pdf_path"]).exists())
            self.assertIn("summary_score", state["quality_scores"])
            self.assertIn("HBM4", state["trl_assessment"])


if __name__ == "__main__":
    unittest.main()
