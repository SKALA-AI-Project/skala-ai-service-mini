from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from urllib.parse import urlparse

from langsmith import traceable
from tavily import TavilyClient

from config import RuntimeConfig
from prompts.search_prompt import build_query
from schemas.search_result import SearchResult


class WebSearchAgent:
    """Tavily 기반 실검색과 테스트용 mock 경로를 함께 처리한다."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.search_config = config.search
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

        return self._collect_live_results(topics, competitors, date_range)

    def _collect_live_results(
        self,
        topics: list[str],
        competitors: list[str],
        date_range: dict[str, str],
    ) -> tuple[list[SearchResult], dict[str, int], bool]:
        """Tavily API를 사용해 실검색을 수행한다.

        - API 예외: 호출 자체가 실패한 경우 → 오류 로그 후 해당 쿼리 건너뜀
        - 빈 결과: 호출은 성공했지만 결과가 없는 경우 → 빈 결과 로그 후 건너뜀
        두 경우 모두 mock으로 대체하지 않고 실패를 명시적으로 기록한다.
        """
        results: list[SearchResult] = []
        domain_cap: dict[str, int] = {}

        for tech in topics:
            for company in competitors:
                for perspective, suffix in self.search_config.perspectives.items():
                    query = build_query(company, tech, suffix)
                    try:
                        response = self.client.search(
                            query=query,
                            topic="news",
                            days=90,
                            max_results=5,
                            include_raw_content=True,
                        )
                        raw_results = response.get("results", [])
                        if not raw_results:
                            # API 호출 성공이지만 빈 결과 — mock 대체 없이 로그만 기록
                            print(f"[LOG] 검색 빈 결과: query={query}")
                            continue

                        for item in raw_results:
                            url = item.get("url", "")
                            domain = urlparse(url).netloc
                            if domain and domain_cap.get(domain, 0) >= self.search_config.domain_cap:
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

                    except Exception as exc:
                        # API 호출 자체가 실패한 경우 — 빈 결과와 구분해 명시적으로 기록
                        print(f"[LOG] 검색 API 오류: query={query}, error={exc}")

        scores = self._score_results(results)
        bias_check = (
            scores["bias_score"] >= self.search_config.bias_score_threshold
            and scores["search_richness"] >= self.search_config.search_richness_threshold
        )
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
        """테스트와 로컬 개발을 위한 대체 경로다. 실서비스 경로에서는 호출하지 않는다."""
        results: list[SearchResult] = []
        source_types = list(self.search_config.source_type_rules.keys())

        for tech in topics:
            for company in competitors:
                for index, (perspective, suffix) in enumerate(self.search_config.perspectives.items()):
                    results.append(
                        self._build_mock_result(
                            tech=tech,
                            company=company,
                            perspective=perspective,
                            suffix=suffix,
                            source_type=source_types[index % len(source_types)],
                            published_date=date_range["to"],
                        )
                    )

        scores = self._score_results(results)
        bias_check = (
            scores["bias_score"] >= self.search_config.bias_score_threshold
            and scores["search_richness"] >= self.search_config.search_richness_threshold
        )
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
        query = build_query(company, tech, suffix)
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
        """config의 source_type_rules를 기준으로 소스 유형을 추정한다."""
        lowered = " ".join([url.lower(), title.lower(), content.lower()])
        for source_type, keywords in self.search_config.source_type_rules.items():
            if any(token in lowered for token in keywords):
                return source_type
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
