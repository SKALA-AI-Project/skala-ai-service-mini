from __future__ import annotations

import unittest
from datetime import date

from config import load_runtime_config, TrlConfig, RuntimeConfig
from agents.trl_analysis_node import TrlAnalysisNode
from agents.web_search_agent import WebSearchAgent
from schemas.search_result import SearchResult


def _make_node(trl_config: TrlConfig | None = None) -> TrlAnalysisNode:
    config = load_runtime_config(use_live_api=False)
    if trl_config is not None:
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
            trl=trl_config,
        )
    return TrlAnalysisNode(config)


def _make_item(
    tech: str = "HBM4",
    company: str = "Samsung",
    content: str = "",
    title: str = "",
) -> SearchResult:
    return SearchResult(
        query=f"{company} {tech}",
        title=title,
        url=f"https://example.com/{company}/{tech}",
        content=content,
        perspective="neutral",
        source_type="news",
        published_date=date.today().isoformat(),
        company=company,
        tech=tech,
    )


class TrlCoverageTest(unittest.TestCase):
    """TRL 분석이 모든 기술·기업 쌍을 채우는지 확인한다."""

    def test_trl_analysis_covers_all_pairs(self) -> None:
        search_agent = WebSearchAgent(load_runtime_config(use_live_api=False))
        search_results, _, _ = search_agent.collect(
            topics=["HBM4", "PIM", "CXL"],
            competitors=["Samsung", "Micron"],
            date_range=search_agent.build_date_range(),
        )

        assessments = TrlAnalysisNode(load_runtime_config(use_live_api=False)).analyze(search_results)

        self.assertEqual(set(assessments.keys()), {"HBM4", "PIM", "CXL"})
        self.assertEqual(set(assessments["HBM4"].keys()), {"Samsung", "Micron"})

    def test_all_required_fields_present(self) -> None:
        """각 TRL 결과에 basis·confidence·evidence·limitation 필드가 있어야 한다."""
        node = _make_node()
        items = [_make_item("HBM4", "Samsung", content="양산 출하 mass production")]
        assessments = node.analyze(items)

        result = assessments["HBM4"]["Samsung"]
        self.assertIn("trl", result)
        self.assertIn("basis", result)
        self.assertIn("confidence", result)
        self.assertIn("evidence", result)
        self.assertIn("limitation", result)


class TrlProductionSignalTest(unittest.TestCase):
    """양산·출하 신호 감지 시 TRL 7+ confirmed로 처리되는지 검증한다."""

    def test_production_keyword_triggers_confirmed(self) -> None:
        node = _make_node()
        items = [_make_item(content="mass production shipment volume production customer delivery")]
        assessments = node.analyze(items)
        result = list(list(assessments.values())[0].values())[0]
        self.assertGreaterEqual(result["trl"], 7)
        self.assertEqual(result["basis"], "confirmed")

    def test_single_production_keyword_gives_trl7(self) -> None:
        node = _make_node()
        items = [_make_item(content="양산 시작 발표")]
        assessments = node.analyze(items)
        result = list(list(assessments.values())[0].values())[0]
        self.assertEqual(result["trl"], 7)

    def test_multiple_production_keywords_give_trl8(self) -> None:
        node = _make_node()
        items = [_make_item(content="양산 출하 mass production shipment customer delivery")]
        assessments = node.analyze(items)
        result = list(list(assessments.values())[0].values())[0]
        self.assertEqual(result["trl"], 8)

    def test_confirmed_basis_has_no_limitation(self) -> None:
        node = _make_node()
        items = [_make_item(content="양산 출하 shipment")]
        assessments = node.analyze(items)
        result = list(list(assessments.values())[0].values())[0]
        self.assertIsNone(result["limitation"])


class TrlIndicatorTest(unittest.TestCase):
    """5개 간접지표 기반 추정 로직을 검증한다."""

    def test_academic_and_patent_gives_trl3_confirmed(self) -> None:
        """논문·특허만 있고 채용 없으면 TRL 3 confirmed."""
        node = _make_node()
        items = [_make_item(content="isscc paper arxiv 특허 patent 출원")]
        assessments = node.analyze(items)
        result = list(list(assessments.values())[0].values())[0]
        self.assertEqual(result["trl"], 3)
        self.assertEqual(result["basis"], "confirmed")

    def test_hiring_and_patent_gives_trl5_estimated(self) -> None:
        """채용 + 특허 시 TRL 5 estimated."""
        node = _make_node()
        items = [_make_item(content="엔지니어 채용 수율 공정 특허 출원 yield patent")]
        assessments = node.analyze(items)
        result = list(list(assessments.values())[0].values())[0]
        self.assertEqual(result["trl"], 5)
        self.assertEqual(result["basis"], "estimated")

    def test_hiring_and_ir_gives_trl6_estimated(self) -> None:
        """채용 + IR 시 TRL 6 estimated."""
        node = _make_node()
        items = [_make_item(content="엔지니어 채용 모집 매출 실적 revenue earnings quarter")]
        assessments = node.analyze(items)
        result = list(list(assessments.values())[0].values())[0]
        self.assertEqual(result["trl"], 6)
        self.assertEqual(result["basis"], "estimated")

    def test_estimated_has_limitation_text(self) -> None:
        """estimated 결과에는 오차 가능성이 limitation에 포함되어야 한다."""
        node = _make_node()
        items = [_make_item(content="특허 출원 patent arxiv")]
        # 채용 없이 특허만 → TRL 4 estimated
        assessments = node.analyze(items)
        result = list(list(assessments.values())[0].values())[0]
        if result["basis"] == "estimated":
            self.assertIsNotNone(result["limitation"])
            self.assertIn("오차", result["limitation"])

    def test_no_signals_gives_low_trl(self) -> None:
        """신호가 없을 때 보수적으로 낮은 TRL이 배정되어야 한다."""
        node = _make_node()
        items = [_make_item(content="general news about technology")]
        assessments = node.analyze(items)
        result = list(list(assessments.values())[0].values())[0]
        self.assertLessEqual(result["trl"], 5)


class TrlSamsungPenaltyTest(unittest.TestCase):
    """Samsung 공개 보수성 패널티가 confidence에 적용되는지 검증한다."""

    def test_samsung_gets_lower_confidence_than_micron(self) -> None:
        """동일 신호로 Samsung은 Micron보다 confidence가 같거나 낮아야 한다."""
        node = _make_node()
        content = "patent 특허 arxiv isscc 엔지니어 채용 매출 실적 파트너십"

        items_samsung = [_make_item("HBM4", "Samsung", content=content)]
        items_micron = [_make_item("HBM4", "Micron", content=content)]

        all_items = items_samsung + items_micron
        assessments = node.analyze(all_items)

        confidence_order = {"high": 3, "medium": 2, "low": 1}
        samsung_c = confidence_order[assessments["HBM4"]["Samsung"]["confidence"]]
        micron_c = confidence_order[assessments["HBM4"]["Micron"]["confidence"]]
        self.assertLessEqual(samsung_c, micron_c)

    def test_samsung_penalty_can_be_disabled(self) -> None:
        """samsung_confidence_penalty=False 시 패널티가 적용되지 않아야 한다."""
        no_penalty_config = TrlConfig(samsung_confidence_penalty=False)
        node = _make_node(no_penalty_config)

        content = "patent 특허 arxiv isscc 엔지니어 채용 매출 실적 파트너십"
        items_samsung = [_make_item("HBM4", "Samsung", content=content)]
        items_micron = [_make_item("HBM4", "Micron", content=content)]

        assessments = node.analyze(items_samsung + items_micron)
        # 패널티 없으면 동일 신호에서 동일 confidence
        self.assertEqual(
            assessments["HBM4"]["Samsung"]["confidence"],
            assessments["HBM4"]["Micron"]["confidence"],
        )


class TrlLimitationTest(unittest.TestCase):
    """limitation 필드가 설계 문서 요구사항대로 채워지는지 검증한다."""

    def test_limitation_mentions_error_range(self) -> None:
        """estimated 결과의 limitation에 ±1~2 단계 오차 표현이 있어야 한다."""
        node = _make_node()
        items = [_make_item(content="특허")]
        assessments = node.analyze(items)
        result = list(list(assessments.values())[0].values())[0]
        if result["basis"] == "estimated":
            self.assertIsNotNone(result["limitation"])
            self.assertIn("오차", result["limitation"])

    def test_samsung_limitation_mentions_conservative(self) -> None:
        """Samsung estimated 결과에는 공개 보수성 언급이 있어야 한다."""
        node = _make_node()
        items = [_make_item("HBM4", "Samsung", content="특허 출원")]
        assessments = node.analyze(items)
        result = assessments["HBM4"]["Samsung"]
        if result["basis"] == "estimated":
            self.assertIsNotNone(result["limitation"])
            self.assertIn("Samsung", result["limitation"])


if __name__ == "__main__":
    unittest.main()
