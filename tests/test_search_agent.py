import unittest

from agents.web_search_agent import WebSearchAgent


class SearchAgentTest(unittest.TestCase):
    """검색 에이전트의 기본 다양성 규칙을 검증한다."""

    def test_search_agent_returns_balanced_mock_results(self) -> None:
        agent = WebSearchAgent()
        results, scores, bias_check = agent.collect(
            topics=["HBM4", "PIM", "CXL"],
            competitors=["Samsung", "Micron"],
            date_range=agent.build_date_range(),
        )

        self.assertEqual(len(results), 18)
        self.assertGreaterEqual(scores["search_richness"], 3)
        self.assertGreaterEqual(scores["bias_score"], 3)
        self.assertTrue(bias_check)


if __name__ == "__main__":
    unittest.main()
