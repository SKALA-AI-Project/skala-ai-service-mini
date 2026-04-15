from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from urllib.parse import urlparse

from langsmith import traceable
from tavily import TavilyClient

from config import RuntimeConfig
from schemas.search_result import SearchResult


class WebSearchAgent:
    """Tavily 기반 실검색과 mock fallback을 함께 처리한다."""

    perspectives = {
        "positive": "시장 선도 전망",
        "negative": "기술 리스크와 지연 요인",
        "neutral": "기술 개발 동향",
    }

    source_types = ["official", "analyst", "academic", "news"]

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.client = TavilyClient(api_key=config.tavily_api_key) if config.tavily_api_key else None

    def build_date_range(self) -> dict[str, str]:
        """최근 3개월 기준 날짜 범위를 생성한다."""
        end_date = date.today()
        start_date = end_date - timedelta(days=90)
        return {"from": start_date.isoformat(), "to": end_date.isoformat()}

    @traceable(name="web_search_collect", run_type="chain")
    def collect(
        self,
        topics: list[str],
        competitors: list[str],
        date_range: dict[str, str],
    ) -> tuple[list[SearchResult], dict[str, int], bool]:
        """검색 결과와 검색 품질 점수를 함께 반환한다."""
        print(
            "[LOG] WebSearchAgent.collect 호출:"
            f" topics={topics}, competitors={competitors},"
            f" use_live_api={self.config.use_live_api}"
        )
        if not self.config.use_live_api or not self.client:
            print("[LOG] WebSearchAgent mock 경로 사용")
            return self._collect_mock_results(topics, competitors, date_range)

        results: list[SearchResult] = []
        domain_cap: dict[str, int] = {}

        # 확증 편향을 줄이기 위해 기술/기업별로 3개 관점 질의를 모두 수행한다.
        for tech in topics:
            for company in competitors:
                for perspective, suffix in self.perspectives.items():
                    query = f"{company} {tech} {suffix}"
                    response = self.client.search(
                        query=query,
                        topic="news",
                        days=90,
                        max_results=5,
                        include_raw_content=True,
                    )

                    for item in response.get("results", []):
                        url = item.get("url", "")
                        domain = urlparse(url).netloc
                        if domain and domain_cap.get(domain, 0) >= 2:
                            continue

                        result = SearchResult(
                            query=query,
                            title=item.get("title", query),
                            url=url,
                            content=item.get("raw_content") or item.get("content", ""),
                            perspective=perspective,  # type: ignore[arg-type]
                            source_type=self._classify_source_type(
                                url=url,
                                title=item.get("title", ""),
                                content=item.get("content", ""),
                            ),  # type: ignore[arg-type]
                            published_date=item.get("published_date", date_range["to"]),
                            company=company,
                            tech=tech,
                        )
                        results.append(result)
                        if domain:
                            domain_cap[domain] = domain_cap.get(domain, 0) + 1

        # API 결과가 비어 있으면 설계 검증 흐름은 유지하되, 로그로 구분 가능하게 mock을 사용한다.
        if not results:
            print("[LOG] Tavily 결과 비어 있음: mock 경로로 대체")
            return self._collect_mock_results(topics, competitors, date_range)

        scores = self._score_results(results)
        bias_check = scores["bias_score"] >= 3 and scores["search_richness"] >= 3
        print(
            "[LOG] WebSearchAgent.collect 완료:"
            f" results={len(results)}, scores={scores}, bias_check={bias_check}"
        )
        return results, scores, bias_check

    def _collect_mock_results(
        self,
        topics: list[str],
        competitors: list[str],
        date_range: dict[str, str],
    ) -> tuple[list[SearchResult], dict[str, int], bool]:
        """실검색이 어려운 경우 테스트와 로컬 개발을 위해 사용하는 대체 경로다."""
        results: list[SearchResult] = []

        for tech in topics:
            for company in competitors:
                for index, (perspective, suffix) in enumerate(self.perspectives.items()):
                    results.append(
                        self._build_mock_result(
                            tech=tech,
                            company=company,
                            perspective=perspective,
                            suffix=suffix,
                            source_type=self.source_types[index % len(self.source_types)],
                            published_date=date_range["to"],
                        )
                    )

        scores = self._score_results(results)
        bias_check = scores["bias_score"] >= 3 and scores["search_richness"] >= 3
        print(
            "[LOG] mock 검색 결과 생성:"
            f" results={len(results)}, scores={scores}, bias_check={bias_check}"
        )
        return results, scores, bias_check

    def _build_mock_result(
        self,
        tech: str,
        company: str,
        perspective: str,
        suffix: str,
        source_type: str,
        published_date: str,
    ) -> SearchResult:
        """설계 검증용 모의 검색 결과를 표준 형태로 만든다."""
        query = f"{company} {tech} {suffix}"
        return SearchResult(
            query=query,
            title=f"{company} {tech} {suffix}",
            url=f"https://example.com/{company.lower()}/{tech.lower()}/{perspective}",
            content=(
                f"{company}의 {tech} 관련 최근 동향을 {perspective} 관점에서 요약한 결과다. "
                "실제 API 연동 전까지는 설계 검증용 모의 데이터로 사용된다."
            ),
            perspective=perspective,  # type: ignore[arg-type]
            source_type=source_type,  # type: ignore[arg-type]
            published_date=published_date,
            company=company,
            tech=tech,
        )

    def _classify_source_type(self, url: str, title: str, content: str) -> str:
        """도메인과 본문 힌트로 소스 유형을 추정한다."""
        lowered = " ".join([url.lower(), title.lower(), content.lower()])
        if any(token in lowered for token in ["samsung.com", "micron.com", "skhynix"]):
            return "official"
        if any(token in lowered for token in ["trendforce", "gartner", "idc", "counterpoint"]):
            return "analyst"
        if any(token in lowered for token in ["arxiv", "ieee", "isscc", "hot chips", "patent"]):
            return "academic"
        if any(token in lowered for token in ["blog", "medium", "substack"]):
            return "blog"
        return "news"

    def _score_results(self, results: list[SearchResult]) -> dict[str, int]:
        """검색 풍부도와 편향 점수를 단순 규칙으로 계산한다."""
        source_type_count = len({item["source_type"] for item in results})
        perspective_counter = Counter(item["perspective"] for item in results)
        total_results = len(results)

        if total_results >= 15 and source_type_count >= 3:
            search_richness = 5
        elif total_results >= 10 and source_type_count >= 2:
            search_richness = 4
        elif total_results >= 7 and source_type_count >= 2:
            search_richness = 3
        elif total_results >= 5:
            search_richness = 2
        else:
            search_richness = 1

        negative_ratio = perspective_counter["negative"] / max(total_results, 1)
        neutral_ratio = perspective_counter["neutral"] / max(total_results, 1)
        if negative_ratio >= 0.2 and neutral_ratio >= 0.2:
            bias_score = 5
        elif negative_ratio >= 0.15:
            bias_score = 4
        elif negative_ratio > 0:
            bias_score = 3
        elif total_results >= 5:
            bias_score = 2
        else:
            bias_score = 1

        return {
            "search_richness": search_richness,
            "bias_score": bias_score,
        }
