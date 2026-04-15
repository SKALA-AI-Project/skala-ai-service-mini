설계 문서 vs 코드 불일치 항목

1. State 필드 정의 (Section 6.1)
항목설계 문서실제 코드비고클래스명StateWorkflowState이름 상이재시도 카운터retry_count: int (단일)websearch_retry_count: int필드명 변경편향 재시도 카운터bias_retry_count: int없음 (별도 State 필드 없음)누락error_log 타입Annotated[List[str], operator.add]list[str]Annotation 미적용search_results 타입List[Dict]list[SearchResult]타입 구체화 (방향은 긍정적)추가 필드없음user_query, report_title, final_report_md_path, metadata설계에 없는 필드 4개 추가
2. Draft 섹션 구성 (Section 4.2.4)
항목설계 문서실제 코드섹션 수7개6개섹션 이름summaryexecutive_summarybackgroundanalysis_backgroundtech_status(없음, investigation_results에 통합 추정)competitor(없음, investigation_results에 통합 추정)trl_assessment(없음, investigation_results에 통합 추정)insightstrategic_implicationsreferencereference(없음)conclusion (코드에만 존재)
3. TRL 간접지표 수 (Section 4.2.3 vs Section 2.3)
항목설계 문서 Section 2.3설계 문서 Section 4.2.3 & 5실제 코드지표 수5종3종5종 (2.3 기준 구현)지표 목록특허·학회·채용·파트너십·IR특허·학회·채용patent·academic·hiring·partnership·IR파트너십·IR 위상주요 지표보조 참고자료 (TRL 산정 미사용)주요 지표로 구현
설계 문서 내부 모순 존재: Section 2.3과 Section 4.2.3/5의 지표 수가 다름. 코드는 Section 2.3(5종)을 따름.

4. Confidence 등급 기준
등급설계 Section 2.3설계 Section 4.2.3 & 5실제 코드High5개 중 4개 이상3개 모두≥4개 (2.3 기준)Medium2~3개2개2~3개Low1개 이하 또는 충돌충돌 또는 1개 이하≤1개
코드는 Section 2.3 기준으로 구현. Section 4.2.3/5와 불일치.

5. SearchResult source_type 값
항목설계 문서 (Section 6.1)실제 코드source_type 허용값paper | news | blogofficial | analyst | academic | news | blog추가 필드없음company, tech 필드 추가
6. 설계에 없는 코드 추가 기능
항목설계 문서실제 코드설계 정합성 검증 루프없음validate_design_mapping() + 별도 재시도 루프 존재LLM 모델 지정명시 없음draft_model: "gpt-4o", judge_model: "gpt-4o-mini"PDF 라이브러리명시 없음 (Pandoc + XeLaTeX 언급)WeasyPrint 사용Formatting Node 실패 시Markdown 보존 + fail 신호동일하게 구현됨 (일치)
요약
불일치 유형항목 수State 필드 불일치 (이름 변경·누락·추가)6건Draft 섹션 수 및 이름 불일치7건TRL 지표 수·위상 불일치 (설계 내부 모순 포함)3건Confidence 기준 불일치 (설계 내부 모순 포함)1건SearchResult 스키마 불일치2건설계에 없는 추가 구현3건
가장 중요한 불일치: Draft 섹션이 설계의 7개 → 코드에서 6개로 줄었고, 섹션 이름이 모두 변경되었습니다. 또한 설계 문서 자체가 Section 2.3(5종 지표)과 Section 4.2.3/5(3종 지표)에서 내부적으로 모순되며, 코드는 Section 2.3을 따릅니다.