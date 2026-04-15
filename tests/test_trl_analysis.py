import unittest

from agents.trl_analysis_node import TrlAnalysisNode
from agents.web_search_agent import WebSearchAgent


class TrlAnalysisTest(unittest.TestCase):
    """TRL 분석이 모든 기술·기업 쌍을 채우는지 확인한다."""

    def test_trl_analysis_covers_all_pairs(self) -> None:
        search_agent = WebSearchAgent()
        search_results, _, _ = search_agent.collect(
            topics=["HBM4", "PIM", "CXL"],
            competitors=["Samsung", "Micron"],
            date_range=search_agent.build_date_range(),
        )

        assessments = TrlAnalysisNode().analyze(search_results)

        self.assertEqual(set(assessments.keys()), {"HBM4", "PIM", "CXL"})
        self.assertEqual(set(assessments["HBM4"].keys()), {"Samsung", "Micron"})


if __name__ == "__main__":
    unittest.main()
