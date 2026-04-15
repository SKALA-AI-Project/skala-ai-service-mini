from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# 사용자 비밀값은 런타임에서만 로드하고, 코드나 로그에 직접 출력하지 않는다.
load_dotenv()


@dataclass
class SearchConfig:
    """검색 관련 설정을 분리한 모듈."""

    perspectives: dict[str, str] = field(
        default_factory=lambda: {
            "positive": "시장 선도 전망",
            "negative": "기술 리스크와 지연 요인",
            "neutral": "기술 개발 동향",
        }
    )
    source_type_rules: dict[str, list[str]] = field(
        default_factory=lambda: {
            "official": ["samsung.com", "micron.com", "skhynix"],
            "analyst": ["trendforce", "gartner", "idc", "counterpoint"],
            "academic": ["arxiv", "ieee", "isscc", "hot chips", "patent"],
            "blog": ["blog", "medium", "substack"],
        }
    )
    domain_cap: int = 2
    bias_retry_max: int = 2
    search_richness_threshold: int = 3
    bias_score_threshold: int = 3


@dataclass
class TrlConfig:
    """TRL 분석 관련 설정."""

    production_keywords: list[str] = field(
        default_factory=lambda: [
            "양산", "출하", "mass production", "shipment", "volume production",
            "customer delivery", "hvm", "high volume manufacturing", "납품",
            "량산", "공급 개시",
        ]
    )
    patent_keywords: list[str] = field(
        default_factory=lambda: [
            "patent", "특허", "출원", "등록", "uspto", "process", "yield",
            "수율", "공정", "kr특허", "jp특허",
        ]
    )
    academic_keywords: list[str] = field(
        default_factory=lambda: [
            "isscc", "hot chips", "arxiv", "conference", "학회", "발표",
            "논문", "research", "paper", "symposium",
        ]
    )
    hiring_keywords: list[str] = field(
        default_factory=lambda: [
            "engineer", "엔지니어", "수율", "yield", "공정", "process",
            "양산", "manufacturing", "production engineer", "채용", "모집",
        ]
    )
    partnership_keywords: list[str] = field(
        default_factory=lambda: [
            "partnership", "파트너십", "supply chain", "공급망", "협력",
            "계약", "customer", "고객사", "납품", "공급", "협약",
        ]
    )
    ir_keywords: list[str] = field(
        default_factory=lambda: [
            "revenue", "매출", "실적", "earnings", "ir", "investor",
            "분기", "quarter", "guidance", "실적발표", "investor day",
        ]
    )
    samsung_confidence_penalty: bool = True
    confidence_high_threshold: int = 4   # 5종 중 4개 이상 일치
    confidence_medium_threshold: int = 2  # 2개 이상 일치


@dataclass
class DraftConfig:
    """보고서 초안 생성 관련 설정."""

    required_sections: list[str] = field(
        default_factory=lambda: [
            "executive_summary",
            "analysis_purpose",
            "analysis_scope",
            "tech_status",
            "investigation_results",
            "conclusion",
            "reference",
        ]
    )
    quality_threshold: int = 3
    draft_retry_max: int = 2
    executive_summary_min: int = 600
    executive_summary_max: int = 800
    section_min_length: int = 1200


@dataclass(frozen=True)
class RuntimeConfig:
    """`.env.example`에 정의된 키를 그대로 구조화한 설정 객체다."""

    openai_api_key: str
    langchain_api_key: str
    langchain_tracing_v2: str
    langchain_endpoint: str
    langchain_project: str
    huggingfacehub_api_token: str
    tavily_api_key: str
    draft_model: str
    judge_model: str
    use_live_api: bool
    search: SearchConfig = field(default_factory=SearchConfig)
    trl: TrlConfig = field(default_factory=TrlConfig)
    draft: DraftConfig = field(default_factory=DraftConfig)


def load_runtime_config(use_live_api: bool = True) -> RuntimeConfig:
    """실행 모드와 환경 변수를 조합해 런타임 설정을 반환한다."""
    return RuntimeConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        langchain_api_key=os.getenv("LANGCHAIN_API_KEY", ""),
        langchain_tracing_v2=os.getenv("LANGCHAIN_TRACING_V2", "true"),
        langchain_endpoint=os.getenv(
            "LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"
        ),
        langchain_project=os.getenv("LANGCHAIN_PROJECT", "SKALA"),
        huggingfacehub_api_token=os.getenv("HUGGINGFACEHUB_API_TOKEN", ""),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        draft_model=os.getenv("DRAFT_MODEL", "gpt-4o"),
        judge_model=os.getenv("JUDGE_MODEL", "gpt-4o-mini"),
        use_live_api=use_live_api,
    )
