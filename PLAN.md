# PLAN.md

## 목표

최근 3개월 내 공개 정보를 바탕으로 HBM4, PIM, CXL의 기술 동향과 경쟁사(Samsung, Micron) 성숙도를 분석하고, TRL 평가와 전략적 시사점을 포함한 PDF 보고서를 자동 생성한다.

## 범위

- 입력: 기술 주제 3종, 경쟁사 2종, 최근 3개월 날짜 범위
  - 기술 주제 3종, 경쟁사 2종, 최근 3개월 날짜 범위는 기본값이며, Supervisor가 사용자 쿼리에서 이를 추출해 재설정할 수 있어야 한다.
- 처리: 검색, 편향 점검, TRL 분석, 초안 생성, 품질 검증, PDF 변환
- 출력: Markdown 보고서 초안, PDF 최종본, 로그

## 피드백 반영 원칙

- `feedbacks/`의 검토 사항을 설계 문서와 1:1로 다시 매핑한 뒤 구현한다.
- mock fallback은 테스트 전용 경로로 제한하고, 실서비스 경로에서는 실패 원인을 명시적으로 남긴다.
- 설정 상수, 프롬프트, 에이전트 책임 범위를 분리해 유지보수성을 높인다.
- 보완 후에는 `design.md` 대응표와 테스트를 함께 갱신한다.

## 단계별 계획

### 1단계. 기반 구성 정리

- `config.py`를 워크플로우별 설정 모듈로 재구성
- 검색 관점(`perspectives`), 소스 분류 규칙, 품질 임계값을 설정 계층으로 이동
- `prompts/` 디렉토리를 문서 폴더가 아니라 실행 프롬프트 자산 기준으로 재정리
- `{목적}_prompt.py` 또는 실행 템플릿 로더 구조 도입

**완료 기준**

- 설정 상수와 실행 로직이 분리됨
- 프롬프트 파일이 실제 코드에서 로드 가능함
- 검색/TRL/보고서 생성이 각자 독립 설정을 가짐

### 2단계. 검색 계층 보완

- `agents/web_search_agent.py`의 query 생성 규칙을 프롬프트/설정 기반으로 분리
- Tavily 검색 실패와 빈 결과를 구분해 예외 처리
- 빈 결과 시 mock 대체가 아니라 오류 기록 또는 재시도 분기로 처리
- 최신성 필터, 도메인 캡, 소스 유형 분류 기준 강화
- `bias_score`, `search_richness`, `bias_check` 계산 규칙을 설계 문서 수준으로 정교화

**피드백 반영 항목**

- `prompts/search/*.md` → 실행용 프롬프트 자산 구조로 개편
- `self.perspectives`를 `config.py`로 이동
- `_classify_source_type` 기준을 설정 계층으로 이동
- 검색 성공/실패/빈 결과를 구분 가능한 상태값 또는 에러 처리 추가
- 워크플로우별 config 분리

**완료 기준**

- 각 기술/기업/관점 조합별 검색 결과가 구조화되어 저장됨
- 검색 실패와 빈 결과가 서로 다른 로그/분기로 처리됨
- bias 재시도와 실패 조건이 분기 처리됨
- 소스 유형 분류와 다양성 계산이 설정 기반으로 동작함

### 3단계. TRL 분석 보완

- `design.md`의 TRL 방법론을 간접지표 3종에서 5종으로 확대 반영
- `agents/trl_analysis_node.py`의 하드코딩 판정을 제거하고 검색 결과 기반 판정으로 교체
- 간접지표 5종:
  - 특허 출원 패턴
  - 학회 발표 패턴
  - 채용 공고 키워드
  - 파트너십·공급망 발표
  - IR·실적 발표 언어
- 양산/출하 신호 감지 시 TRL 7 이상 `confirmed` 처리
- 5개 지표 일치도에 따라 `confidence` 산정
- Samsung 공개 보수성 패널티 로직 유지
- `prompts/trl/assessment_prompt.md`를 새 방법론 기준으로 갱신

**피드백 반영 항목**

- `_infer_trl()`에 검색 결과 items 자체를 입력으로 사용
- 지표 신호 개수 계산 함수 추가
- 양산/출하 신호 감지 함수 추가
- confidence 계산을 5개 지표 기준으로 재정의
- limitation에 ±1~2 단계 오차 가능성 반영

**완료 기준**

- 모든 기술/기업 조합에 대해 TRL JSON이 생성됨
- `basis`, `confidence`, `evidence`, `limitation` 필드가 누락 없이 채워짐
- TRL 4~6은 5개 간접지표 기반 `estimated`로 설명 가능함

### 4단계. 보고서 초안 및 포맷 보완

- 7개 섹션 초안 생성 품질 기준 유지
- `formatting_node.py`에 TRL 4~6 추정 면책 문구 자동 삽입
- PDF 변환 실패 시 Markdown 보존 + fail 신호 반환
- `report_workflow.py`의 최종 검증 루프에서 `draft_retry_count` 중복 증가 제거
  - `retry_count` 변수는 삭제하고 `draft_retry_count`, `websearch_retry_count`만으로 각각의 시도 횟수를 관리
- 포맷팅 실패를 `error_log`에 명시적으로 기록

**피드백 반영 항목**

- TRL 추정 문구가 최종 보고서에 반드시 반영되도록 후처리 추가
- `FormattingNode.export()` 반환값을 성공 여부 포함 구조로 변경
- 설계 외 카운터 조작 제거

**완료 기준**

- `summary/background/tech_status/competitor/trl_assessment/insight/reference` 7개 섹션이 모두 채워짐
- TRL 4~6 추정 면책 문구가 자동 삽입됨
- PDF 실패 시 Markdown은 남고 오류는 로그로 기록됨

### 5단계. 검증 체계 보강

- `tests/test_search_agent.py`를 검색 실패/빈 결과/도메인 캡/편향 점수 케이스까지 확장
- `tests/test_trl_analysis.py`를 5개 간접지표 기준 케이스로 확장
- `tests/test_report_workflow.py`를 단일 E2E에서 다중 케이스 세트로 확장
- `docs/설계구현_매핑.md`를 피드백 반영 후 다시 갱신
- `design.md` 변경이 필요하면 TRL 방법론 수정안 반영

**피드백 반영 항목**

- 보고서 워크플로우 테스트 수 대폭 확장
- 포맷팅 실패/섹션 누락/편향 미통과/설계 매핑 실패 케이스 추가
- `design.md` 수정 요청사항 검토 및 문서 동기화

**완료 기준**

- 핵심 실패 시나리오가 테스트로 커버됨
- 성공 기준 6개가 모두 검증됨
- 피드백 문서 3종의 조치 항목이 체크리스트로 소거됨

## 성공 기준

- HBM4, PIM, CXL 모두 포함
- Samsung, Micron 모두 비교
- 최근 3개월 이내 자료 포함
- TRL 평가 명시
- 7개 섹션 구조 완비
- URL 참조 가능

## 위험 요소

- 검색 API 품질 또는 수집량 부족
- TRL 4-6 구간의 직접 검증 불가
- PDF 렌더링 환경 의존성
- 특정 기업의 정보 공개 편차
- 설계 문서와 실제 구현 로직 간 버전 차이

## 즉시 다음 작업

1. `feedbacks/websearch_feedback.md` 기준으로 검색 설정/프롬프트 구조 개편
2. `feedbacks/trl_analysis_feedback.md` 기준으로 TRL 5지표 로직 반영
3. `feedbacks/report_feedback.md` 기준으로 formatting/workflow 실패 처리 보완
4. 테스트를 검색, TRL, 보고서 3축으로 세분화
5. 필요 시 `design.md` TRL 방법론 수정안 반영
