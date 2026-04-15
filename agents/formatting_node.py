from __future__ import annotations

from pathlib import Path


class FormattingNode:
    """Markdown 산출물 저장과 PDF 파일 생성을 담당한다."""

    def export(
        self,
        markdown: str,
        output_dir: Path,
        allow_pdf: bool = True,
    ) -> tuple[str, str, bool]:
        """Markdown과 PDF 산출물 경로 및 성공 여부를 반환한다."""
        print(f"[LOG] FormattingNode.export 호출: output_dir={output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "technology_strategy_report.md"
        pdf_path = output_dir / "technology_strategy_report.pdf"

        final_markdown = self._inject_trl_disclaimer(markdown)
        markdown_path.write_text(final_markdown, encoding="utf-8")
        print(f"[LOG] Markdown 저장 완료: {markdown_path}")

        if not allow_pdf or "https://example.com/" in final_markdown:
            print("[LOG] PDF 생성 중단: mock 데이터 기반 실행이므로 오류 처리")
            return str(markdown_path), "", False

        try:
            self._write_minimal_pdf(pdf_path)
        except Exception:
            print("[LOG] PDF 생성 실패")
            return str(markdown_path), "", False

        print(f"[LOG] PDF 저장 완료: {pdf_path}")
        return str(markdown_path), str(pdf_path), True

    def _inject_trl_disclaimer(self, markdown: str) -> str:
        """TRL 4~6 추정 문구가 있으면 면책 안내를 보고서에 삽입한다."""
        if "추정" not in markdown:
            return markdown

        disclaimer = (
            "> 주의: TRL 4~6 평가는 공개 정보 기반 간접지표에 따른 추정치이며, "
            "실제 기술 성숙도와 차이가 있을 수 있습니다."
        )
        target_heading = "# 4. 결론"
        if target_heading in markdown:
            return markdown.replace(target_heading, f"{disclaimer}\n\n{target_heading}", 1)
        return f"{markdown}\n\n{disclaimer}"

    def _write_minimal_pdf(self, pdf_path: Path) -> None:
        """외부 라이브러리 없이 열 수 있는 최소 PDF를 만든다."""
        pdf_bytes = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 70 >>
stream
BT
/F1 12 Tf
36 100 Td
(Report generated. See markdown for full Korean content.) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000241 00000 n 
0000000362 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
432
%%EOF
"""
        pdf_path.write_bytes(pdf_bytes)
