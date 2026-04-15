"""초안 품질 평가에 사용하는 프롬프트 템플릿."""
from __future__ import annotations

QUALITY_SYSTEM_PROMPT = (
    "너는 기술 보고서 품질 평가자다. 반드시 JSON 스키마에 맞게만 응답한다."
)

QUALITY_USER_PROMPT_TEMPLATE = """
아래 보고서를 1~5점으로 평가하라.

평가 항목:
- summary_score: SUMMARY 분량(600~800자)과 핵심 메시지 완성도 — 첫 문장부터 각 경쟁사·기술의 핵심 동향이 두괄식으로 제시되었는지 포함
- coverage_score: 요구 목차(7개 섹션)와 하위 항목 완결도
- evidence_score: URL 근거와 주장 연결성 (모든 주장에 출처 존재 여부)
- consistency_score: 섹션 간 논리 일관성 및 TRL 표기 일치 여부

채점 기준:
- 5점: 완전 충족
- 4점: 소폭 미흡 (1건 이하 결함)
- 3점: 부분 충족 (2~3건 결함)
- 2점: 상당 부분 미흡
- 1점: 기준 미달

보고서:
{markdown}
""".strip()
