# PLAN.md

## 목표

최근 3개월 내 공개 정보를 바탕으로 HBM4, PIM, CXL의 기술 동향과 경쟁사(Samsung, Micron) 성숙도를 분석하고, TRL 평가와 전략적 시사점을 포함한 PDF 보고서를 자동 생성한다.

## 범위

- 입력: 기술 주제 3종, 경쟁사 2종, 최근 3개월 날짜 범위
- 처리: 검색, 편향 점검, TRL 분석, 초안 생성, 품질 검증, PDF 변환
- 출력: Markdown 보고서 초안, PDF 최종본, 로그

## 단계별 계획

### 1단계. 기반 구성

- `schemas/`에 shared state와 입출력 스키마 정의
- `prompts/`에 검색/평가/초안 작성 프롬프트 템플릿 분리
- `workflows/`에 Supervisor 기반 LangGraph 골격 구성

**완료 기준**

- 상태 모델과 각 노드 계약이 코드로 고정됨
- 최소 실행 경로가 빈 입력 없이 동작함

### 2단계. 검색 계층

- Web Search Agent 구현
- 기술/기업/관점별 쿼리 생성기 구현
- 소스 유형 분류, 도메인 캡, 최신성 필터 적용
- `bias_score`, `search_richness`, `bias_check` 계산

**완료 기준**

- 각 기술/기업 조합별 검색 결과가 구조화되어 저장됨
- bias 재시도와 실패 조건이 분기 처리됨

### 3단계. TRL 분석

- TRL 1-3, 4-6, 7-9 구간별 판정 로직 구현
- 간접지표 기반 `estimated` 판정과 confidence 로직 구현
- 기업별 limitation 문구 정책 반영

**완료 기준**

- 모든 기술/기업 조합에 대해 TRL JSON이 생성됨
- `basis`, `confidence`, `evidence`, `limitation` 필드가 누락 없이 채워짐

### 4단계. 보고서 초안 생성

- 7개 섹션 초안 생성기 구현
- quality score 평가 프롬프트 구현
- 기준 미달 시 draft 재생성 루프 구현

**완료 기준**

- `summary/background/tech_status/competitor/trl_assessment/insight/reference` 7개 섹션이 모두 채워짐
- evidence와 reference 매칭 검증 가능

### 5단계. 포맷팅과 산출

- Markdown 템플릿 정리
- PDF 변환 파이프라인 구성
- 실패 시 Markdown 보존 및 오류 로그 저장

**완료 기준**

- 최종 Markdown과 PDF가 `outputs/reports/`에 생성됨
- 변환 실패 시 재현 가능한 로그가 남음

### 6단계. 검증

- 골든 시나리오 1건 이상으로 E2E 테스트 추가
- 누락 섹션, 편향 미통과, PDF 변환 실패 케이스 점검
- README 산출물 형식에 맞춘 최종 문서 정리

**완료 기준**

- 핵심 실패 시나리오가 테스트로 커버됨
- 성공 기준 6개가 모두 검증됨

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

## 즉시 다음 작업

1. `schemas/`에 state 모델 정의
2. `workflows/`에 Supervisor 그래프 골격 작성
3. `prompts/`에 검색 쿼리 템플릿과 보고서 템플릿 작성
4. `agents/`에 Web Search Agent부터 구현 시작
