# 디렉토리 구조

이 프로젝트는 Supervisor 중심 Agentic Workflow를 기준으로 아래 구조를 사용한다.

```text
.
├── AGENTS.md
├── PLAN.md
├── DIRECTORY_STRUCTURE.md
├── README.md
├── contexts/
│   ├── 01_프로젝트개요.md
│   ├── 02_워크플로우.md
│   ├── 03_에이전트정의.md
│   ├── 04_trl방법론.md
│   ├── 05_상태정의.md
│   └── 06_보고서규격.md
├── design.md
├── agents/
│   ├── supervisor.py
│   ├── web_search_agent.py
│   ├── draft_generation_agent.py
│   ├── formatting_node.py
│   ├── hitl_node.py
│   └── trl_analysis_node.py
├── workflows/
│   └── report_workflow.py
├── schemas/
│   ├── state.py
│   ├── search_result.py
│   ├── trl_assessment.py
│   └── report_sections.py
├── prompts/
│   ├── search/
│   │   ├── official_sources.md
│   │   ├── analyst_sources.md
│   │   └── risk_queries.md
│   ├── trl/
│   │   └── assessment_prompt.md
│   ├── draft/
│   │   ├── report_prompt.md
│   │   └── quality_eval_prompt.md
│   └── formatting/
│       └── pdf_template.md
├── data/
│   ├── raw/
│   └── processed/
├── outputs/
│   ├── logs/
│   └── reports/
└── tests/
    ├── test_search_agent.py
    ├── test_trl_analysis.py
    └── test_report_workflow.py
```

## 디렉토리 목적

- `contexts/`: 설계 맥락 문서와 작업 기준
- `agents/`: 각 에이전트와 노드 구현
- `workflows/`: LangGraph 또는 orchestration 로직
- `schemas/`: shared state와 구조화 응답 모델
- `prompts/`: 검색, TRL 분석, 초안 생성, 품질 평가 프롬프트
- `data/raw/`: 원본 수집 자료 캐시
- `data/processed/`: 정제 결과, 중간 산출물
- `outputs/logs/`: 실행 로그와 오류 로그
- `outputs/reports/`: Markdown/PDF 최종 산출물
- `tests/`: 단위 및 E2E 테스트

## 권장 구현 순서

1. `contexts/` 확인
2. `schemas/`
3. `prompts/`
4. `agents/`
5. `workflows/`
6. `tests/`
7. `outputs/` 연동
