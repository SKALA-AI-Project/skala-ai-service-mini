from __future__ import annotations

import os
from collections import Counter
from datetime import date, timedelta

from schemas.search_result import SearchResult


class WebSearchAgent:
    """실제 키가 없어도 동작 가능한 검색 수집 계층이다."""

    perspectives = {
        "positive": "시장 선도 전망",
        "negative": "기술 리스크와 지연 요인",
        "neutral": "기술 개발 동향",
    }

    source_types = ["official", "analyst", "academic", "news"]

    def __init__(self) -> None:
        # .env를 읽지 않고 프로세스 환경 변수만 사용한다.
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.huggingfacehub_api_token = os.getenv("HUGGINGFACEHUB_API_TOKEN", "")

    def collect(
        self,
        topics: list[str],
        competitors: list[str],
        date_range: dict[str, str],
    ) -> tuple[list[SearchResult], dict[str, int], bool]:
        """검색 결과와 검색 품질 점수를 함께 반환한다."""
        results: list[SearchResult] = []

        # 실제 API 키가 없을 때도 설계 흐름을 검증할 수 있도록 모의 결과를 만든다.
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
        return results, scores, bias_check

    def build_date_range(self) -> dict[str, str]:
        """최근 3개월 기준 날짜 범위를 생성한다."""
        end_date = date.today()
        start_date = end_date - timedelta(days=90)
        return {"from": start_date.isoformat(), "to": end_date.isoformat()}

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
