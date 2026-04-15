from __future__ import annotations

from pathlib import Path


class FormattingNode:
    """Markdown 산출물 저장과 PDF 파일 생성을 담당한다."""

    def export(self, markdown: str, output_dir: Path) -> tuple[str, str]:
        """Markdown과 PDF 산출물 경로를 반환한다."""
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "technology_strategy_report.md"
        pdf_path = output_dir / "technology_strategy_report.pdf"

        markdown_path.write_text(markdown, encoding="utf-8")
        self._write_minimal_pdf(pdf_path)
        return str(markdown_path), str(pdf_path)

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
