"""TRL 평가 신호 탐지 패턴과 LLM 프롬프트 템플릿."""
from __future__ import annotations

SYSTEM_PROMPT = """
너는 반도체 기술 성숙도(TRL) 평가 전문가다.
수집된 검색 결과에서 특허·학회·채용·파트너십·IR 신호를 식별하고
TRL 1~9 구간과 basis(confirmed/estimated), confidence(high/medium/low),
evidence, limitation을 반환한다.

규칙:
- TRL 1~3: 논문·특허 확인 시 confirmed
- TRL 4~6: 간접지표 기반이면 estimated, 반드시 "추정"과 한계 명시
- TRL 7~9: 양산·출하·고객사 납품 공식 발표 시 confirmed
- Samsung은 공개 보수적이므로 동일 조건에서 confidence 한 단계 하향
- limitation에는 ±1~2 단계 오차 가능성을 반드시 포함한다
""".strip()

USER_PROMPT_TEMPLATE = """
기술: {tech}
기업: {company}

검색 결과:
{search_snippets}

위 자료에서 아래 5개 간접지표 신호를 확인하고 TRL을 판정하라.

1. 특허 출원 패턴 (특허 출원·등록, 공정·수율 키워드 이동)
2. 학회 발표 패턴 (ISSCC·Hot Chips·arxiv 발표 빈도·수치 구체성)
3. 채용 공고 키워드 (연구원 → 공정·수율·양산 엔지니어 변화)
4. 파트너십·공급망 발표 (고객사 계약, 공급 협약, IR 자료)
5. IR·실적 발표 언어 (매출 언급, 분기 가이던스 변화)

판정 기준:
- 양산·출하 신호가 명확하면 TRL 7 이상 confirmed
- 지표 4종 이상 동일 방향: confidence=high
- 지표 2~3종 동일 방향: confidence=medium
- 지표 1종 이하 또는 충돌: confidence=low
- Samsung: 동일 조건에서 confidence 한 단계 하향
""".strip()
