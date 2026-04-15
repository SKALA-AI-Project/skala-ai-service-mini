# TRL 평가 프롬프트

- 입력: 기술명, 경쟁사명, 최근 검색 결과, 간접지표
- 출력: `trl`, `basis`, `confidence`, `evidence`, `limitation`

## 규칙

- TRL 1~3: 논문·특허 확인 시 `confirmed`
- TRL 4~6: 간접지표 기반이면 `estimated`
- TRL 7~9: 양산·출하·공식 발표가 있으면 `confirmed`
- `estimated`면 보고서에 반드시 한계를 적는다.
