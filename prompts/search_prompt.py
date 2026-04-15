"""웹 검색 쿼리 생성 템플릿과 도메인 우선순위 상수."""
from __future__ import annotations

# 기업 공식 채널 도메인 우선순위
PRIORITY_DOMAINS: list[str] = [
    "news.skhynix.co.kr",
    "semiconductor.samsung.com",
    "investors.micron.com",
]

# 제3자 시장조사기관 출처
ANALYST_SOURCES: list[str] = ["TrendForce", "CounterPoint", "Gartner", "IDC"]

SYSTEM_PROMPT = (
    "너는 반도체 기술 시장 정보를 수집하는 검색 전문가다. "
    "주어진 기술과 기업에 대해 공식 발표, 시장조사 자료, 리스크 관점 자료를 균형 있게 수집한다."
)


def build_query(company: str, tech: str, perspective_suffix: str) -> str:
    """기업·기술·관점 조합으로 검색 쿼리를 생성한다.
    반도체 맥락 키워드를 추가해 PIM 등 약어 충돌을 방지한다.
    """
    return f"{company} {tech} semiconductor memory {perspective_suffix}"
