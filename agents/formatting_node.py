from __future__ import annotations

from pathlib import Path

import aspose.words as aw


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
            if pdf_path.exists():
                pdf_path.unlink()
            return str(markdown_path), "", False

        try:
            self._write_pdf_from_markdown(markdown_path, pdf_path)
        except Exception as exc:
            print(f"[LOG] PDF 생성 실패: {exc}")
            if pdf_path.exists():
                pdf_path.unlink()
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

    def _write_pdf_from_markdown(self, markdown_path: Path, pdf_path: Path) -> None:
        """Aspose Words로 Markdown 파일을 직접 읽어 PDF로 변환한다."""
        load_options = aw.loading.LoadOptions()
        load_options.encoding = "utf-8"
        document = aw.Document(str(markdown_path), load_options)
        document.save(str(pdf_path), aw.SaveFormat.PDF)
