from __future__ import annotations

from typing import Literal, TypedDict


class SearchResult(TypedDict):
    """검색 결과 한 건의 정규화 구조를 정의한다."""

    query: str
    title: str
    url: str
    content: str
    perspective: Literal["positive", "negative", "neutral"]
    source_type: Literal["official", "analyst", "academic", "news", "blog"]
    published_date: str
    company: str
    tech: str
