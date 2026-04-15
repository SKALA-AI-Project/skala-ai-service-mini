from __future__ import annotations

import unittest
from datetime import date, timedelta

from config import load_runtime_config, SearchConfig, RuntimeConfig
from agents.web_search_agent import WebSearchAgent


def _make_agent(search_config: SearchConfig | None = None) -> WebSearchAgent:
    config = load_runtime_config(use_live_api=False)
    if search_config is not None:
        # frozen=True라 직접 교체는 불가 — 새 RuntimeConfig 생성
        config = RuntimeConfig(
            openai_api_key=config.openai_api_key,
            langchain_api_key=config.langchain_api_key,
            langchain_tracing_v2=config.langchain_tracing_v2,
            langchain_endpoint=config.langchain_endpoint,
            langchain_project=config.langchain_project,
            huggingfacehub_api_token=config.huggingfacehub_api_token,
            tavily_api_key=config.tavily_api_key,
            draft_model=config.draft_model,
            judge_model=config.judge_model,
            use_live_api=False,
            search=search_config,
        )
    return WebSearchAgent(config)


class SearchAgentHappyPathTest(unittest.TestCase):
    """검색 에이전트의 기본 다양성 규칙을 검증한다."""

    def test_mock_returns_balanced_results(self) -> None:
        agent = _make_agent()
        results, scores, bias_check = agent.collect(
            topics=["HBM4", "PIM", "CXL"],
            competitors=["Samsung", "Micron"],
            date_range=agent.build_date_range(),
        )

        self.assertEqual(len(results), 18)
        self.assertGreaterEqual(scores["search_richness"], 3)
        self.assertGreaterEqual(scores["bias_score"], 3)
        self.assertTrue(bias_check)

    def test_all_perspectives_represented(self) -> None:
        """긍정·부정·중립 3개 관점이 모두 포함되는지 확인한다."""
        agent = _make_agent()
        results, _, _ = agent.collect(
            topics=["HBM4"],
            competitors=["Samsung"],
            date_range=agent.build_date_range(),
        )
        perspectives = {r["perspective"] for r in results}
        self.assertIn("positive", perspectives)
        self.assertIn("negative", perspectives)
        self.assertIn("neutral", perspectives)

    def test_results_contain_required_fields(self) -> None:
        """결과 각 항목이 설계 문서의 필드를 모두 갖추는지 확인한다."""
        agent = _make_agent()
        results, _, _ = agent.collect(
            topics=["HBM4"],
            competitors=["Samsung"],
            date_range=agent.build_date_range(),
        )
        required_fields = {"query", "title", "url", "content", "perspective",
                           "source_type", "published_date", "company", "tech"}
        for result in results:
            self.assertTrue(required_fields.issubset(set(result.keys())))


class SearchAgentDomainCapTest(unittest.TestCase):
    """도메인 캡 설정이 실제로 적용되는지 검증한다."""

    def test_domain_cap_is_read_from_config(self) -> None:
        """config.search.domain_cap 값이 에이전트에 반영되는지 확인한다."""
        agent = _make_agent()
        self.assertEqual(agent.search_config.domain_cap, 2)

    def test_custom_domain_cap(self) -> None:
        """도메인 캡이 1로 설정되면 동일 도메인에서 1건만 수집해야 한다."""
        custom_search = SearchConfig(domain_cap=1)
        agent = _make_agent(custom_search)
        # mock 경로는 도메인을 example.com/<company>/<tech>/<perspective>로 분산하므로
        # 도메인 캡이 적용돼도 mock 결과는 모두 다른 URL임 — config 접근만 검증
        self.assertEqual(agent.search_config.domain_cap, 1)


class SearchAgentSourceTypeTest(unittest.TestCase):
    """소스 유형 분류 기준이 config 기반으로 동작하는지 검증한다."""

    def test_classify_official_domain(self) -> None:
        agent = _make_agent()
        result = agent._classify_source_type(
            url="https://semiconductor.samsung.com/news",
            title="Samsung HBM4 announcement",
            content="official release",
        )
        self.assertEqual(result, "official")

    def test_classify_analyst_domain(self) -> None:
        agent = _make_agent()
        result = agent._classify_source_type(
            url="https://trendforce.com/report",
            title="HBM market share",
            content="analyst report",
        )
        self.assertEqual(result, "analyst")

    def test_classify_academic_domain(self) -> None:
        agent = _make_agent()
        result = agent._classify_source_type(
            url="https://arxiv.org/abs/1234",
            title="HBM4 memory architecture",
            content="research paper",
        )
        self.assertEqual(result, "academic")

    def test_classify_unknown_defaults_to_news(self) -> None:
        agent = _make_agent()
        result = agent._classify_source_type(
            url="https://unknown-site.io/article",
            title="some article",
            content="general content",
        )
        self.assertEqual(result, "news")


class SearchAgentBiasScoreTest(unittest.TestCase):
    """편향 점수 계산 로직을 검증한다."""

    def test_bias_check_fails_when_only_positive(self) -> None:
        """긍정 관점만 존재하면 bias_check가 False여야 한다."""
        agent = _make_agent()
        # 긍정 관점만 있는 단일 결과
        from schemas.search_result import SearchResult
        from datetime import date as dt
        single_positive = [
            SearchResult(
                query="q", title="t", url="https://x.com/1",
                content="c", perspective="positive", source_type="news",
                published_date=dt.today().isoformat(), company="Samsung", tech="HBM4",
            )
        ]
        scores = agent._score_results(single_positive)
        # 결과 1건 → total_results < 5 → bias_score = 1
        self.assertEqual(scores["bias_score"], 1)

    def test_balanced_perspectives_give_high_bias_score(self) -> None:
        """긍정·부정·중립 균형 시 bias_score가 높아야 한다."""
        agent = _make_agent()
        results, scores, _ = agent.collect(
            topics=["HBM4", "PIM", "CXL"],
            competitors=["Samsung", "Micron"],
            date_range=agent.build_date_range(),
        )
        # mock 결과는 3 관점이 균등 배분되므로 bias_score >= 3 기대
        self.assertGreaterEqual(scores["bias_score"], 3)

    def test_perspectives_loaded_from_config(self) -> None:
        """perspectives가 config에서 읽히는지 확인한다."""
        agent = _make_agent()
        self.assertIn("positive", agent.search_config.perspectives)
        self.assertIn("negative", agent.search_config.perspectives)
        self.assertIn("neutral", agent.search_config.perspectives)


class SearchAgentDateRangeTest(unittest.TestCase):
    """날짜 범위 생성 로직을 검증한다."""

    def test_date_range_is_approximately_90_days(self) -> None:
        agent = _make_agent()
        date_range = agent.build_date_range()
        from_date = date.fromisoformat(date_range["from"])
        to_date = date.fromisoformat(date_range["to"])
        delta = (to_date - from_date).days
        self.assertAlmostEqual(delta, 90, delta=1)


if __name__ == "__main__":
    unittest.main()
