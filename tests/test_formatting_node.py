import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agents.formatting_node import FormattingNode


class FormattingNodeTest(unittest.TestCase):
    """Markdown 산출물의 PDF 렌더링 동작을 검증한다."""

    def test_export_creates_real_pdf_for_live_markdown(self) -> None:
        markdown = "\n\n".join(
            [
                "# EXECUTIVE SUMMARY\n실제 PDF 렌더링 검증을 위한 본문이다.",
                "# 1. 분석 배경\n한글 문단이 PDF 안에 실제로 들어가야 한다.",
                "# 2. 기술 현황\nHBM4와 PIM에 대한 실제 렌더링 테스트다.",
                "# 3. 조사 결과\n## 3.1 Samsung\n## 3.1.1 Samsung 동향\n본문.",
                "# 4. 결론\n결론 문단.",
                "# REFERENCE\n- https://www.example.org/reference",
            ]
        )

        with TemporaryDirectory() as temp_dir:
            node = FormattingNode()
            markdown_path, pdf_path, success = node.export(
                markdown=markdown,
                output_dir=Path(temp_dir),
                allow_pdf=True,
            )

            self.assertTrue(success)
            self.assertTrue(Path(markdown_path).exists())
            self.assertTrue(Path(pdf_path).exists())
            self.assertGreater(Path(pdf_path).stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
