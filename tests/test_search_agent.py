from __future__ import annotations

import unittest
from datetime import date, timedelta

from config import load_runtime_config, SearchConfig, RuntimeConfig
from agents.web_search_agent import WebSearchAgent
from schemas.search_result import SearchResult


def _make_agent(search_config: SearchConfig | None = None) -> WebSearchAgent:
    config = load_runtime_config(use_live_api=False)
    if search_config is not None:
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


def _make_result(
    perspective: str = "neutral",
    source_type: str = "news",
    company: str = "Samsung",
    tech: str = "HBM4",
    url: str = "https://example.com",
) -> SearchResult:
    return SearchResult(
        query=f"{company} {tech}",
        title=f"{company} {tech} news",
        url=url,
        content="content",
        perspective=perspective,  # type: ignore[arg-type]
        source_type=source_type,  # type: ignore[arg-type]
        published_date=date.today().isoformat(),
        company=company,
        tech=tech,
    )


class SearchAgentNoApiKeyTest(unittest.TestCase):
    """API 키 없을 때 빈 결과를 반환하고 HITL로 넘기는지 검증한다."""

    def test_collect_returns_empty_without_api_key(self) -> None:
        """Tavily API 키가 없으면 빈 결과를 반환해야 한다."""
        agent = _make_agent()
        results, scores, bias_check = agent.collect(
            topics=["HBM4", "PIM"],
            competitors=["Samsung"],
            date_range=agent.build_date_range(),
        )
        self.assertEqual(results, [])
        self.assertFalse(bias_check)

    def test_collect_scores_zero_without_api_key(self) -> None:
        """API 키 없는 경우 품질 점수가 0으로 반환되어야 한다."""
        agent = _make_agent()
        _, scores, _ = agent.collect(
            topics=["HBM4"],
            competitors=["Samsung"],
            date_range=agent.build_date_range(),
        )
        self.assertEqual(scores["search_richness"], 0)
        self.assertEqual(scores["bias_score"], 0)


class SearchAgentDateRangeTest(unittest.TestCase):
    """날짜 범위 생성 로직을 검증한다."""

    def test_date_range_is_approximately_90_days(self) -> None:
        agent = _make_agent()
        date_range = agent.build_date_range()
        from_date = date.fromisoformat(date_range["from"])
        to_date = date.fromisoformat(date_range["to"])
        delta = (to_date - from_date).days
        self.assertAlmostEqual(delta, 90, delta=1)


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
    """편향 점수 계산 로직을 직접 결과 목록으로 검증한다."""

    def test_bias_check_fails_when_only_positive(self) -> None:
        """긍정 관점만 존재하면 bias_score가 낮아야 한다."""
        agent = _make_agent()
        single_positive = [_make_result(perspective="positive")]
        scores = agent._score_results(single_positive)
        # 결과 1건 → total_results < 5 → bias_score = 1
        self.assertEqual(scores["bias_score"], 1)

    def test_balanced_perspectives_give_high_bias_score(self) -> None:
        """긍정·부정·중립 균형 시 bias_score >= 3이어야 한다."""
        agent = _make_agent()
        results = (
            [_make_result(perspective="positive", url=f"https://p.com/{i}") for i in range(4)]
            + [_make_result(perspective="negative", url=f"https://n.com/{i}") for i in range(4)]
            + [_make_result(perspective="neutral", url=f"https://neu.com/{i}") for i in range(4)]
        )
        scores = agent._score_results(results)
        self.assertGreaterEqual(scores["bias_score"], 3)

    def test_perspectives_loaded_from_config(self) -> None:
        """perspectives가 config에서 읽히는지 확인한다."""
        agent = _make_agent()
        self.assertIn("positive", agent.search_config.perspectives)
        self.assertIn("negative", agent.search_config.perspectives)
        self.assertIn("neutral", agent.search_config.perspectives)


class SearchAgentDomainCapTest(unittest.TestCase):
    """도메인 캡 설정이 config에서 올바르게 로드되는지 검증한다."""

    def test_domain_cap_is_read_from_config(self) -> None:
        agent = _make_agent()
        self.assertEqual(agent.search_config.domain_cap, 2)

    def test_custom_domain_cap(self) -> None:
        custom_search = SearchConfig(domain_cap=1)
        agent = _make_agent(custom_search)
        self.assertEqual(agent.search_config.domain_cap, 1)


class SearchAgentScoreRichnessTest(unittest.TestCase):
    """검색 풍부도 점수 계산을 직접 결과 목록으로 검증한다."""

    def test_high_richness_requires_15_results_3_source_types(self) -> None:
        """15건 이상 + 소스 유형 3개 이상이면 search_richness == 5여야 한다."""
        agent = _make_agent()
        results = (
            [_make_result(source_type="news", url=f"https://news.com/{i}") for i in range(6)]
            + [_make_result(source_type="analyst", url=f"https://analyst.com/{i}") for i in range(5)]
            + [_make_result(source_type="official", url=f"https://official.com/{i}") for i in range(4)]
        )
        scores = agent._score_results(results)
        self.assertEqual(scores["search_richness"], 5)

    def test_low_richness_below_5_results(self) -> None:
        """5건 미만이면 search_richness == 1이어야 한다."""
        agent = _make_agent()
        results = [_make_result(url=f"https://x.com/{i}") for i in range(3)]
        scores = agent._score_results(results)
        self.assertEqual(scores["search_richness"], 1)


if __name__ == "__main__":
    unittest.main()
