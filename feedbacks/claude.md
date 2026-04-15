# Claude 코드 검토 결과

검토 기준: `design.md`, `PLAN.md`
검토 일자: 2026-04-15
대상 파일: `agents/`, `workflows/`, `schemas/`, `tests/`

---

## ✅ 잘 반영된 항목

| 영역 | 내용 |
|------|------|
| **State 구조** | `WorkflowState`가 design.md 6.1 대부분 반영. `retry_count` 제거 후 `websearch_retry_count` / `draft_retry_count` 분리 (PLAN.md 4단계) |
| **Supervisor** | T1~T5 순서 제어, `validate_search_coverage` / `validate_trl_coverage` / `validate_draft` / `validate_design_mapping` 4종 검증 메서드, 재시도 max 2회 |
| **Web Search Agent** | 3개 관점(positive/negative/neutral) 쿼리, 소스 유형 분류, 도메인 캡(max 2건), bias_check / search_richness 점수 계산 |
| **Draft Generation Agent** | 7개 섹션 생성, LLM quality_scores 4종, `basis=estimated` → "추정" 서술, 재시도 max 2회, LLM / 규칙 기반 dual path |
| **Formatting Node** | TRL 4~6 면책 문구 자동 삽입 (`_inject_trl_disclaimer`), PDF 실패 시 Markdown 보존 + fail 신호 + error_log 기록 |
| **워크플로우 제어** | 검색 2회 → HITL, 초안 2회 → 강제 종료, 설계 검증 루프, LangSmith `@traceable` 추적 |
| **쿼리 기반 범위 추출** | 사용자 쿼리에서 기술/경쟁사/날짜 자동 파싱 (`extract_request_scope`) |

---

## ❌ 미반영 또는 부분 반영 항목

### 1. TRL 분석의 하드코딩 판정 (가장 중요한 미반영)

**파일**: `agents/trl_analysis_node.py:48`

`_infer_trl()`이 실제 검색 결과를 보지 않고 tech 이름만으로 고정값 반환:

```python
# 현재 구현 - 검색 결과 무관, tech 이름 하드코딩
if tech == "HBM4":
    return 7, "confirmed", "medium", None
```

PLAN.md 3단계에서 요구한 내용이 미반영:

- `_infer_trl()`에 검색 결과 items 자체를 입력으로 사용 → **없음**
- 간접지표 3~5종 기반 추정 로직 (특허/학회/채용) → **없음**
- 양산·출하 신호 감지 함수 → **없음**
- confidence 계산을 지표 일치 개수 기반으로 재정의 → **없음**

---

### 2. 섹션 이름이 design.md와 불일치

**파일**: `agents/supervisor.py:20`, `agents/draft_generation_agent.py:181`

| design.md | 현재 구현 |
|-----------|----------|
| `summary` | `executive_summary` |
| `background` | `analysis_purpose` + `analysis_scope` |
| `competitor` | `investigation_results` |
| `trl_assessment` | (investigation_results 내부에 통합) |
| `insight` | `conclusion` |

7개 섹션 수는 유지되나 이름이 전면 변경됨. `design.md` 문서와의 추적이 어려워짐.
→ 코드에 맞게 design.md를 업데이트하거나, 매핑 주석을 추가해야 함.

---

### 3. perspectives / source_type 분류 기준이 config에 없음

**파일**: `agents/web_search_agent.py:17`

PLAN.md 2단계: `self.perspectives`와 `_classify_source_type` 기준을 `config.py`로 이동 → **여전히 클래스 속성/하드코딩**

```python
# 현재 구현 - config 분리 안 됨
perspectives = {
    "positive": "시장 선도 전망",
    "negative": "기술 리스크와 지연 요인",
    "neutral": "기술 개발 동향",
}
```

---

### 4. prompts/ 파일이 실제 코드에서 로드되지 않음

**관련**: PLAN.md 1단계

`prompts/*.md` 파일들이 존재하지만 `agents/draft_generation_agent.py`의 프롬프트는 코드 내 하드코딩 문자열로 관리됨. 프롬프트 수정 시 코드를 직접 수정해야 해 유지보수성이 낮음.

---

### 5. 설계 검증 루프에서 draft_retry_count 중복 증가 가능성

**파일**: `workflows/report_workflow.py:216`

```python
# 초안 루프에서 이미 draft_retry_count가 2에 도달한 상태로
# 설계 검증 루프에 진입하면 즉시 break → 재시도 기회 없음
if state["draft_retry_count"] >= 2:
    break
```

PLAN.md 4단계에서 "중복 증가 제거" 요구했으나, 두 루프에서 같은 카운터를 공유해 설계 검증 후 재시도가 의도대로 동작하지 않을 수 있음.

---

### 6. HITL Node가 골격만 구현

**파일**: `agents/hitl_node.py:9`

```python
def review(self, state: WorkflowState) -> bool:
    return True  # 무조건 승인 — 담당자 UI 연동 없음
```

design.md 4.2.5: bias_check 2회 재시도 후 담당자가 직접 검토하고 수정 지시 또는 승인 판단 → 현재는 자동 승인만 처리.

---

### 7. 테스트 커버리지 부족

PLAN.md 5단계에서 확장을 요구했으나 미반영:

| 테스트 파일 | 현황 | 누락 케이스 |
|------------|------|------------|
| `tests/test_search_agent.py` | happy path 1개 | 도메인 캡 초과, 편향 실패, 빈 결과 구분 |
| `tests/test_trl_analysis.py` | 커버리지 체크 1개 | 간접지표 기반 추정, Samsung 패널티 |
| `tests/test_report_workflow.py` | 2개 케이스 | 포맷팅 실패, 섹션 누락, HITL 트리거 |

---

## 우선순위 요약

| 우선순위 | 항목 | 근거 |
|---------|------|------|
| 🔴 High | TRL 하드코딩 → 검색 결과 기반으로 교체 | design.md 핵심 방법론, PLAN.md 3단계 |
| 🟡 Medium | 섹션 이름 정렬 또는 design.md 업데이트 | 문서-코드 추적 가능성 |
| 🟡 Medium | draft_retry_count 중복 증가 버그 수정 | 설계 검증 루프 재시도 누락 위험 |
| 🟢 Low | perspectives / source_type → config 이동 | 유지보수성 |
| 🟢 Low | prompts/ 파일을 코드에서 로드 | 유지보수성 |
| 🟢 Low | 테스트 케이스 확장 | 안정성 |
