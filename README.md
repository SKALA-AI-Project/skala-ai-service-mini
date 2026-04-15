# SK하이닉스 기술 전략 보고서 자동 생성 시스템

경쟁사(Samsung, Micron)의 HBM4 · PIM · CXL 기술 동향을 웹에서 수집하고, TRL 기반 성숙도 평가와 전략적 시사점을 포함한 보고서를 자동으로 생성하는 Agentic Workflow입니다.

## Overview

- **Objective** : 반도체 기술 분야 경쟁사 모니터링을 자동화하여 SK하이닉스 R&D 전략 수립에 필요한 근거 기반 보고서를 생성한다.
- **Method** : Supervisor 중심 순차 실행 워크플로우 — 웹 검색 → TRL 분석 → 초안 생성 → 품질 검증 → PDF 출력
- **Tools** : LangChain, LangGraph, OpenAI GPT-4o, Tavily Search API, WeasyPrint, LangSmith

## Features

- 기술·경쟁사 범위를 사용자 쿼리에서 자동 추출하고, 미입력 시 기본값(HBM4·PIM·CXL / Samsung·Micron) 사용
- Tavily API 기반 긍정·부정·중립 다관점 웹 검색 및 편향 검증
- 간접지표 5종(특허출원 / 학술발표 / 채용공고 / 파트너십 / IR 언급) 기반 TRL 자동 평가
- 프레임 섹션 + 경쟁사별 조사 결과 + 전략적 시사점을 분리 호출하는 3단계 LLM 초안 생성
- Supervisor가 섹션별 경쟁사·기술 키워드 커버리지를 자동 검증하고, 미달 시 보완 context와 함께 재생성
- 검색 품질 미달 시 HITL(Human-in-the-Loop) 개입 요청
- Markdown + WeasyPrint PDF 이중 출력, 표지에 조사 기간·작성자 포함
- LangSmith를 통한 전체 워크플로우 실행 추적

## Tech Stack

| Category    | Details                                         |
|-------------|-------------------------------------------------|
| Framework   | LangChain, LangGraph, Python 3.11+              |
| LLM         | GPT-4o (draft), GPT-4o-mini (supervisor/title)  |
| Search      | Tavily Search API                               |
| Output      | WeasyPrint (PDF), Markdown                      |
| Monitoring  | LangSmith tracing                               |
| Test        | pytest                                          |

## Agents

- **SupervisorAgent** : 쿼리 범위 추출, 단계별 품질 검증(커버리지·TRL·섹션·설계 매핑), 재생성 제어
- **WebSearchAgent** : Tavily 기반 기술·경쟁사별 다관점 검색, 편향 점수 계산
- **TrlAnalysisNode** : 검색 결과에서 간접지표를 파악하여 TRL 레벨·근거·한계 평가
- **DraftGenerationAgent** : 3단계 LLM 호출(프레임 / 경쟁사별 조사 결과 / 전략적 시사점)로 보고서 초안 생성
- **FormattingNode** : Markdown → HTML → WeasyPrint PDF 변환, 커버 페이지 생성
- **HitlNode** : 검색 품질 기준 미달 시 사람 검토 요청 (비대화형 환경에서 자동 승인)

## Workflow

```
사용자 쿼리
    │
    ▼
Supervisor: 기술·경쟁사·기간 범위 추출
    │
    ▼
WebSearchAgent: 다관점 웹 검색 (최대 3회 재시도 → HITL)
    │
    ▼
TrlAnalysisNode: 기술 성숙도 평가
    │
    ▼
DraftGenerationAgent: 보고서 초안 생성 (최대 3회 재시도)
    │
    ▼
Supervisor: 설계 검증 (커버리지·URL 수·최신성) → 미달 시 재생성
    │
    ▼
FormattingNode: Markdown + PDF 출력
```

## Directory Structure

```
skala-ai-service-mini/
├── agents/
│   ├── supervisor.py              # 워크플로우 제어 및 품질 검증
│   ├── web_search_agent.py        # Tavily 웹 검색 및 편향 검증
│   ├── trl_analysis_node.py       # TRL 기반 기술 성숙도 평가
│   ├── draft_generation_agent.py  # LLM 보고서 초안 생성
│   ├── formatting_node.py         # Markdown → PDF 변환
│   └── hitl_node.py               # Human-in-the-Loop 검토
├── prompts/
│   ├── draft_prompt.py            # 보고서 초안 생성 프롬프트
│   └── quality_prompt.py          # 초안 품질 평가 프롬프트
├── schemas/
│   ├── state.py                   # 워크플로우 상태 TypedDict
│   ├── search_result.py           # 검색 결과 스키마
│   ├── trl_assessment.py          # TRL 평가 스키마
│   └── report_sections.py         # 보고서 섹션 스키마
├── workflows/
│   └── report_workflow.py         # 워크플로우 진입점 및 실행 루프
├── tests/
│   ├── test_report_workflow.py    # 워크플로우 E2E 테스트
│   └── test_formatting_node.py    # PDF 렌더링 테스트
├── icons/                         # 커버 페이지 로고 이미지
├── data/                          # 데이터 디렉터리 (gitkeep)
├── app.py                         # Gradio 기반 실행 UI
├── config.py                      # 환경 변수 및 런타임 설정
├── pyproject.toml                 # 프로젝트 메타데이터 및 pytest 설정
├── requirements.txt               # 의존성 패키지 목록
└── .env.example                   # 환경 변수 템플릿
```

## Getting Started

**1. 의존성 설치**
```bash
pip install -r requirements.txt
```

**2. 환경 변수 설정**
```bash
cp .env.example .env
# .env 파일에 아래 키를 입력
# OPENAI_API_KEY=...
# TAVILY_API_KEY=...
# LANGCHAIN_API_KEY=...  (LangSmith 사용 시)
```

**3. 워크플로우 실행**
```bash
# 기본 실행 (HBM4·PIM·CXL / Samsung·Micron)
python workflows/report_workflow.py --live

# 쿼리 지정
python workflows/report_workflow.py --live --query "최근 6개월 HBM4와 PIM Samsung 분석"

# 작성자 및 출력 경로 지정
python workflows/report_workflow.py --live \
  --writer 김세림 남희정 최지호 \
  --output outputs/reports
```

**4. 테스트 실행 (오프라인 mock)**
```bash
pytest
```

## Contributors

- 김세림 : Prompt Engineering, Agent Design
- 남희정 : Workflow Design, TRL Analysis
- 최지호 : Report Generation, Output Formatting
