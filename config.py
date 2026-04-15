from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


# 사용자 비밀값은 런타임에서만 로드하고, 코드나 로그에 직접 출력하지 않는다.
load_dotenv()


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
