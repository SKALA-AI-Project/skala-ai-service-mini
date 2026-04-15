# PLAN.md

## 목표

최근 3개월 내 공개 정보를 바탕으로 HBM4, PIM, CXL의 기술 동향과 경쟁사(Samsung, Micron) 성숙도를 분석하고, TRL 평가와 전략적 시사점을 포함한 PDF 보고서를 자동 생성한다.

---

## ✅ 이미 수정 완료된 항목 (2026-04-15 기준)

| 항목 | 수정 내용 |
|------|-----------|
| Tavily `days=90` 하드코딩 | `date_range["from"]` 기준으로 `search_days` 동적 계산 |
| TRL 하드코딩 판정 | tech 이름 고정값 → indicator 5종 기반 추정 로직으로 교체 |
| `draft_retry_count` 중복 증가 | 설계 검증 루프에 `design_retry` 별도 카운터 적용 |
| `investigation_results` 단일 필드 압축 | 경쟁사별 독립 LLM 호출로 분리 (`CompetitorSectionOutput`) |
| 분석 목적/범위 중복 섹션 | `analysis_background` 단일 섹션으로 통합 |

---

## 🔴 우선순위 1 — 로직 오류 (즉시 수정)

### P1-1. Query 텍스트 text_blob 오염 → TRL false positive 균등 발생
**파일**: `agents/trl_analysis_node.py` (text_blob 구성 부분)
**문제**: `text_blob`에 `item['query']`를 포함시켜 Samsung·Micron이 동일한 쿼리 구조를 쓰므로 indicator 탐지 결과가 같아짐. 실제 검색 내용 차이가 없어도 동일 TRL로 수렴.
**수정**: `text_blob`에서 `item['query']` 제거 — `title + content`만 사용

---

### P1-2. `signal_count` 이중 계산 + 키워드 집합 불일치
**파일**: `agents/trl_analysis_node.py`
**문제**:
- `_detect_indicator()` → config 키워드 사용 (올바름)
- `_count_indicator_signals()` → 하드코딩된 `indicator_keywords` 클래스 속성 사용 (불일치)
- `analyze()`가 `_detect_indicator`를 직접 호출해 signal_count를 재계산하므로 `_infer_trl()` 반환값 signal_count는 `_`로 버려짐

**수정**: `_count_indicator_signals()` 제거. `analyze()`에서 계산한 `detected` dict로 signal_count를 직접 도출해 `_infer_trl()`에 전달

---

### P1-3. hiring/production 키워드 중복 → 오탐으로 TRL 잘못 상승
**파일**: `config.py`
**문제**: `hiring_keywords`에 `"양산"`, `"manufacturing"` 포함 → 채용공고 문서에서 `_count_production_signals()`가 양산 신호로 오탐 → TRL 7/8 confirmed 잘못 산정
**수정**: `hiring_keywords`에서 생산 관련 키워드(`"양산"`, `"manufacturing"`, `"production engineer"`) 제거. 채용 고유 키워드만 유지

---

### P1-4. quality_prompt 분량 기준이 config와 충돌 → 불필요한 재생성 루프
**파일**: `prompts/quality_prompt.py`
**문제**:
- 초안 생성 프롬프트 → 600~800자 요구 (config 기준)
- quality judge 프롬프트 → 450~550자 기준으로 평가
- LLM이 지시대로 600자 쓰면 `summary_score`가 낮아져 재생성 루프 불필요하게 반복

**수정**: `quality_prompt.py`의 `summary_score` 기준을 600~800자로 일치화

---

## 🟡 우선순위 2 — 품질 저하 (다음 스프린트)

### P2-1. 검색 쿼리 의미 제약 부족 + 무관 기사 유입
**파일**: `prompts/search_prompt.py`, `agents/web_search_agent.py`
**문제**: 쿠키 기사, NHL 기사 등 반도체와 무관한 문서 유입 확인 (`final_state.json` 검증)
**수정 방향**:
1. `build_query()`에 반도체 맥락 강제 키워드 추가 (semiconductor, memory 조건)
2. `_collect_live_results()`에 콘텐츠 관련성 필터 추가 — topic 키워드가 title/content에 없으면 제외

---

### P2-2. PIM·CXL 전용 최소 수집 건수 미보장
**파일**: `agents/supervisor.py`
**문제**: HBM4 검색이 풍부해도 PIM·CXL 결과가 빈약하면 bias_check 통과 가능
**수정 방향**: `validate_search_coverage()`에 기술별 최소 결과 수 검증 추가 (기술당 최소 3건)

---

### P2-3. Mock content에 TRL indicator 키워드 없음
**파일**: `agents/web_search_agent.py`
**문제**: `_build_mock_result()`의 content에 patent/hiring/IR/academic/partnership 키워드가 없어 mock 환경에서 모든 기업이 동일한 TRL fallback 산정
**수정**: 기업·기술·관점 조합별로 indicator 키워드를 mock content에 포함

---

### P2-4. 설계 검증 기준 형식화 문제
**파일**: `agents/supervisor.py`
**문제**: `validate_design_mapping()`이 산출물 존재·품질 키 여부만 확인. 최신성·URL 근거 매핑 미검증
**수정 방향**:
- 검색 결과 `published_date` 기준 최신성 비율 검증
- `reference` 섹션 URL 수 vs search_results 수 비율 검증

---

## 🟢 우선순위 3 — 개선 (여유 있을 때)

### P3-1. HITL 실효성 — 무조건 True 반환
**파일**: `agents/hitl_node.py`
**수정 방향**: 터미널 `input()`으로 담당자가 `y/n` 판단하도록 변경. 실제 UI 연동은 추후.

---

### P3-2. 섹션 이름 design.md 불일치
**현황**: 코드는 `executive_summary`, `analysis_background`, `investigation_results`, `conclusion` 사용. design.md는 `summary`, `background`, `competitor`, `insight` 등 다른 명칭 사용.
**수정 방향**: design.md를 현재 코드 기준으로 업데이트 (코드 변경 없음, 문서 정렬만)

---

### P3-3. 테스트 커버리지 확장
**추가 필요한 케이스**:
- `test_search_agent.py`: 도메인 캡 초과, 편향 실패, 무관 기사 필터
- `test_trl_analysis.py`: text_blob query 제거 후 TRL 재검증, hiring/production 분리 검증
- `test_report_workflow.py`: quality_score 충돌 수정 후 재생성 루프 미발생 검증

---

## 실행 순서

```
[즉시]
P1-4 quality 기준 충돌 수정       → 재생성 루프 오작동 제거
P1-1 text_blob query 제거         → TRL 판정 신뢰도 핵심
P1-2 signal_count 통일            → P1-1과 함께
P1-3 hiring/production 키워드 분리 → 오탐 방지

[다음 스프린트]
P2-3 mock content 키워드 추가     → 테스트 환경 신뢰도
P2-1 쿼리 필터 + 관련성 검증     → 검색 품질
P2-2 기술별 최소 수집 검증       → 커버리지 보장
P2-4 설계 검증 강화              → 검증 실효성

[여유 시]
P3-1 HITL 터미널 입력
P3-2 design.md 문서 정렬
P3-3 테스트 케이스 확장
```
