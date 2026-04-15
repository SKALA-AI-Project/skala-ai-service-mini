from __future__ import annotations

import base64
import re
from datetime import date
from pathlib import Path

from weasyprint import HTML


# ---------------------------------------------------------------------------
# SK Hynix brand palette (orange edition)
# ---------------------------------------------------------------------------
_DARK = "#1B2B4B"        # deep navy-dark  — cover bg, strong headings
_ORANGE = "#E85D04"      # primary orange  — H1 border, accent bar, buttons
_AMBER = "#F4A261"       # lighter orange  — secondary accent
_CREAM = "#FFF8F3"       # warm off-white  — alternate row bg, blockquote bg
_BORDER = "#E8D5C4"      # warm beige      — borders, dots
_TEXT_DARK = "#1A1A2E"   # near-black      — strong text
_TEXT_BODY = "#2D3748"   # dark slate      — body text

# A4 content-area height = 297mm − top_margin(25mm) − bottom_margin(25mm) = 247mm
_COVER_HEIGHT = "247mm"

# Project root (two levels up from this file: agents/ → project root)
_PROJECT_ROOT = Path(__file__).parent.parent


def _load_icon_base64() -> str:
    """hynix_icon.png를 base64로 인코딩한다. 파일이 없으면 빈 문자열을 반환한다."""
    icon_path = _PROJECT_ROOT / "icons" / "hynix_icon.png"
    if icon_path.exists():
        return base64.b64encode(icon_path.read_bytes()).decode()
    return ""


class FormattingNode:
    """Markdown 산출물 저장과 PDF 파일 생성을 담당한다."""

    def export(
        self,
        markdown: str,
        output_dir: Path,
        allow_pdf: bool = True,
        report_title: str = "",
        report_subtitle: str = "",
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
            self._write_pdf_from_markdown(markdown_path, pdf_path, report_title, report_subtitle)
        except Exception as exc:
            print(f"[LOG] PDF 생성 실패: {exc}")
            if pdf_path.exists():
                pdf_path.unlink()
            return str(markdown_path), "", False

        print(f"[LOG] PDF 저장 완료: {pdf_path}")
        return str(markdown_path), str(pdf_path), True

    # ------------------------------------------------------------------
    # TRL disclaimer injection
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # PDF generation (HTML-based)
    # ------------------------------------------------------------------

    def _write_pdf_from_markdown(
        self, markdown_path: Path, pdf_path: Path, report_title: str, report_subtitle: str = ""
    ) -> None:
        """Markdown을 전문 HTML로 변환한 후 WeasyPrint로 PDF로 저장한다."""
        markdown_text = markdown_path.read_text(encoding="utf-8")
        html_content = self._build_html_report(markdown_text, report_title, report_subtitle)
        HTML(string=html_content).write_pdf(str(pdf_path))

    # ------------------------------------------------------------------
    # HTML assembly
    # ------------------------------------------------------------------

    def _build_html_report(self, markdown: str, report_title: str, report_subtitle: str = "") -> str:
        """Markdown 전체를 전문 HTML 보고서로 변환한다."""
        today_str = date.today().strftime("%Y년 %m월 %d일")
        headings = self._extract_headings(markdown)
        icon_b64 = _load_icon_base64()
        cover_html = self._build_cover_html(today_str, report_title, report_subtitle)
        toc_html = self._build_toc_html(headings)
        body_html = self._markdown_to_html_body(markdown, headings)
        css = self._get_report_css()
        icon_element = self._build_icon_element(icon_b64)

        return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8"/>
  <style>
{css}
  </style>
</head>
<body>
{icon_element}
{cover_html}
{toc_html}
{body_html}
</body>
</html>"""

    # ------------------------------------------------------------------
    # Page-header icon (WeasyPrint running element)
    # ------------------------------------------------------------------

    def _build_icon_element(self, icon_b64: str) -> str:
        """모든 페이지 우측 상단에 반복 출력될 아이콘 요소를 생성한다."""
        if not icon_b64:
            return ""
        data_url = f"data:image/png;base64,{icon_b64}"
        return f'<div class="page-header-icon-runner"><img src="{data_url}" alt="SK hynix"/></div>'

    # ------------------------------------------------------------------
    # Cover page
    # ------------------------------------------------------------------

    def _build_cover_html(self, today_str: str, report_title: str, report_subtitle: str = "") -> str:
        """표지 페이지 HTML을 생성한다.
        cover-page height = content-area 높이(247mm)로 고정해
        cover-bottom-bar가 반드시 1페이지 하단에 위치하도록 한다.
        """
        raw_title = report_title or "경쟁사 기술 동향 분석 보고서"
        title_text = raw_title if raw_title.endswith("보고서") else f"{raw_title} 보고서"
        subtitle_html = (
            f'<div class="cover-subtitle">{report_subtitle}</div>'
            if report_subtitle
            else ""
        )
        return f"""
<div class="cover-page">
  <div class="cover-top-bar"></div>
  <div class="cover-content">
    <div class="cover-company">SK hynix</div>
    <div class="cover-divider"></div>
    <div class="cover-title">{title_text}</div>
    {subtitle_html}
    <div class="cover-meta">
      <table class="cover-meta-table">
        <tr>
          <td class="meta-label">작성일</td>
          <td class="meta-value">{today_str}</td>
        </tr>
      </table>
    </div>
  </div>
  <div class="cover-bottom-bar">
    <span class="cover-bottom-text">본 보고서는 AI를 활용하여 작성되었습니다.</span>
  </div>
</div>
"""

    # ------------------------------------------------------------------
    # Table of Contents
    # ------------------------------------------------------------------

    def _extract_headings(self, markdown: str) -> list[tuple[int, str, str]]:
        """Markdown에서 헤딩 목록을 (level, text, id) 형태로 추출한다."""
        headings: list[tuple[int, str, str]] = []
        counter = 0
        for line in markdown.splitlines():
            m = re.match(r"^(#{1,4})\s+(.*)", line.strip())
            if m:
                level = len(m.group(1))
                text = m.group(2).strip()
                counter += 1
                headings.append((level, text, f"h{counter}"))
        return headings

    def _build_toc_html(self, headings: list[tuple[int, str, str]]) -> str:
        """목차 페이지 HTML을 생성한다. WeasyPrint target-counter로 페이지 번호를 자동 삽입한다."""
        items: list[str] = []
        for level, text, hid in headings:
            items.append(
                f'<li class="toc-item toc-level-{level}">'
                f'<a class="toc-link" href="#{hid}">{text}</a>'
                f'<a class="toc-page-num" href="#{hid}"> </a>'
                f"</li>"
            )
        return f"""
<div class="toc-page">
  <h1 class="toc-title">목 차</h1>
  <ul class="toc-list">
    {''.join(items)}
  </ul>
</div>
"""

    # ------------------------------------------------------------------
    # Body HTML
    # ------------------------------------------------------------------

    def _markdown_to_html_body(
        self, markdown: str, headings: list[tuple[int, str, str]]
    ) -> str:
        """Markdown 텍스트를 구조화된 HTML로 변환한다. 헤딩에 id를 부여한다."""
        heading_queue = list(headings)
        heading_index = 0

        lines = markdown.splitlines()
        html_parts: list[str] = []
        in_blockquote = False
        in_ul = False
        in_table = False
        table_rows: list[str] = []

        def flush_table() -> None:
            nonlocal table_rows
            if not table_rows:
                return
            html_parts.append('<table class="data-table">')
            for i, row in enumerate(table_rows):
                cells = [c.strip() for c in row.strip().strip("|").split("|")]
                tag = "th" if i == 0 else "td"
                html_parts.append(
                    "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"
                )
            html_parts.append("</table>")
            table_rows.clear()

        def close_inlines() -> None:
            nonlocal in_ul, in_blockquote
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            if in_blockquote:
                html_parts.append("</blockquote>")
                in_blockquote = False

        def next_heading_id() -> str:
            nonlocal heading_index
            if heading_index < len(heading_queue):
                _, _, hid = heading_queue[heading_index]
                heading_index += 1
                return hid
            return ""

        for line in lines:
            stripped = line.strip()

            # --- Table ---
            if stripped.startswith("|"):
                if not in_table:
                    close_inlines()
                    in_table = True
                if re.match(r"^\|[\s\-:|]+\|", stripped):
                    continue
                table_rows.append(stripped)
                continue
            else:
                if in_table:
                    flush_table()
                    in_table = False

            # --- Blank line ---
            if not stripped:
                close_inlines()
                html_parts.append("<p class='spacer'></p>")
                continue

            # --- Headings ---
            h4 = re.match(r"^####\s+(.*)", stripped)
            h3 = re.match(r"^###\s+(.*)", stripped)
            h2 = re.match(r"^##\s+(.*)", stripped)
            h1 = re.match(r"^#\s+(.*)", stripped)

            if h4:
                close_inlines()
                hid = next_heading_id()
                html_parts.append(f'<h4 id="{hid}">{self._inline(h4.group(1))}</h4>')
                continue
            if h3:
                close_inlines()
                hid = next_heading_id()
                html_parts.append(f'<h3 id="{hid}">{self._inline(h3.group(1))}</h3>')
                continue
            if h2:
                close_inlines()
                hid = next_heading_id()
                html_parts.append(f'<h2 id="{hid}">{self._inline(h2.group(1))}</h2>')
                continue
            if h1:
                close_inlines()
                hid = next_heading_id()
                html_parts.append(f'<h1 id="{hid}">{self._inline(h1.group(1))}</h1>')
                continue

            # --- Blockquote ---
            bq = re.match(r"^>\s?(.*)", stripped)
            if bq:
                if in_ul:
                    html_parts.append("</ul>")
                    in_ul = False
                if not in_blockquote:
                    html_parts.append('<blockquote class="disclaimer">')
                    in_blockquote = True
                html_parts.append(f"<p>{self._inline(bq.group(1))}</p>")
                continue
            else:
                if in_blockquote:
                    html_parts.append("</blockquote>")
                    in_blockquote = False

            # --- List item ---
            li = re.match(r"^[-*]\s+(.*)", stripped)
            if li:
                if not in_ul:
                    html_parts.append('<ul class="report-list">')
                    in_ul = True
                content = li.group(1)
                url_match = re.match(r"(https?://\S+)", content)
                if url_match:
                    url = url_match.group(1)
                    html_parts.append(f'<li><a class="ref-link" href="{url}">{url}</a></li>')
                else:
                    html_parts.append(f"<li>{self._inline(content)}</li>")
                continue
            else:
                if in_ul:
                    html_parts.append("</ul>")
                    in_ul = False

            # --- Regular paragraph ---
            html_parts.append(f"<p>{self._inline(stripped)}</p>")

        close_inlines()
        if in_table:
            flush_table()

        return "\n".join(html_parts)

    @staticmethod
    def _inline(text: str) -> str:
        """인라인 Markdown (bold, italic, code)을 HTML로 변환한다."""
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        text = re.sub(r"`(.+?)`", r'<code class="inline-code">\1</code>', text)
        return text

    # ------------------------------------------------------------------
    # CSS
    # ------------------------------------------------------------------

    @staticmethod
    def _get_report_css() -> str:
        return f"""
    /* ── Global ─────────────────────────────────────────────────── */
    @page {{
      size: A4;
      margin: 25mm 25mm 25mm 30mm;
      @top-right {{
        content: element(pageHeader);
        vertical-align: bottom;
      }}
      @bottom-center {{
        content: counter(page);
        font-family: 'Malgun Gothic', Arial, sans-serif;
        font-size: 9pt;
        color: #9CA3AF;
      }}
    }}
    /* 표지(1페이지)에는 아이콘·페이지 번호 없음 */
    @page:first {{
      @top-right     {{ content: none; }}
      @bottom-center {{ content: none; }}
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', 'Noto Sans KR',
                   Arial, sans-serif;
      font-size: 10pt;
      color: {_TEXT_BODY};
      line-height: 1.7;
      background: #ffffff;
    }}

    /* ── Running header icon ─────────────────────────────────────── */
    .page-header-icon-runner {{
      position: running(pageHeader);
      text-align: right;
    }}
    .page-header-icon-runner img {{
      height: 66px;
      width: auto;
    }}

    /* ── Cover Page ─────────────────────────────────────────────── */
    /* height = A4(297mm) − top(25mm) − bottom(25mm) = 247mm */
    .cover-page {{
      height: {_COVER_HEIGHT};
      display: flex;
      flex-direction: column;
      background: #ffffff;
      page-break-after: always;
    }}
    .cover-top-bar {{
      height: 12px;
      background: {_DARK};
      flex-shrink: 0;
    }}
    .cover-content {{
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 0 40px;
    }}
    .cover-company {{
      font-size: 14pt;
      font-weight: 700;
      color: {_ORANGE};
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 20px;
    }}
    .cover-divider {{
      width: 80px;
      height: 4px;
      background: {_AMBER};
      margin-bottom: 28px;
    }}
    .cover-title {{
      font-size: 22pt;
      font-weight: 700;
      color: {_DARK};
      line-height: 1.3;
      margin-bottom: 12px;
    }}
    .cover-subtitle {{
      font-size: 13pt;
      font-weight: 400;
      color: {_ORANGE};
      margin-bottom: 36px;
      letter-spacing: 0.02em;
    }}
    .cover-meta-table {{
      border-collapse: collapse;
      min-width: 320px;
    }}
    .cover-meta-table tr {{
      border-bottom: 1px solid {_BORDER};
    }}
    .meta-label {{
      font-size: 9pt;
      color: #6B7280;
      padding: 8px 24px 8px 0;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      white-space: nowrap;
    }}
    .meta-value {{
      font-size: 10pt;
      color: {_TEXT_DARK};
      padding: 8px 0;
    }}
    .cover-bottom-bar {{
      background: {_DARK};
      padding: 14px 40px;
      flex-shrink: 0;
    }}
    .cover-bottom-text {{
      font-size: 8pt;
      color: rgba(255,255,255,0.75);
    }}

    /* ── TOC Page ────────────────────────────────────────────────── */
    .toc-page {{
      page-break-before: always;
      page-break-after: always;
      padding-top: 10mm;
    }}
    h1.toc-title {{
      font-size: 18pt;
      font-weight: 700;
      color: {_DARK};
      margin-bottom: 24px;
      padding-bottom: 10px;
      border-bottom: 2px solid {_ORANGE};
    }}
    .toc-list {{
      list-style: none;
      padding: 0;
      margin: 0;
    }}
    .toc-item {{
      display: flex;
      align-items: baseline;
      border-bottom: 1px dotted {_BORDER};
    }}
    .toc-link {{
      text-decoration: none;
      color: {_TEXT_BODY};
      flex: 1;
    }}
    .toc-link::after {{
      content: leader('.');
      color: {_BORDER};
    }}
    .toc-page-num {{
      text-decoration: none;
      color: {_TEXT_DARK};
      font-weight: 600;
      white-space: nowrap;
      padding-left: 6px;
    }}
    .toc-page-num::after {{
      content: target-counter(attr(href), page);
    }}
    .toc-level-1 {{
      margin-top: 10px;
      padding: 5px 0;
    }}
    .toc-level-1 .toc-link {{
      font-size: 11pt;
      font-weight: 700;
      color: {_DARK};
    }}
    .toc-level-2 {{
      padding: 3px 0 3px 16px;
    }}
    .toc-level-2 .toc-link {{
      font-size: 10pt;
      font-weight: 600;
      color: {_TEXT_DARK};
    }}
    .toc-level-3 {{
      padding: 2px 0 2px 32px;
    }}
    .toc-level-3 .toc-link {{
      font-size: 9.5pt;
      color: {_TEXT_BODY};
    }}
    .toc-level-4 {{
      padding: 2px 0 2px 48px;
    }}
    .toc-level-4 .toc-link {{
      font-size: 9pt;
      color: #6B7280;
    }}

    /* ── Headings ───────────────────────────────────────────────── */
    h1 {{
      font-size: 14pt;
      font-weight: 700;
      color: {_DARK};
      margin-top: 28px;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 2px solid {_ORANGE};
      page-break-after: avoid;
    }}
    h2 {{
      font-size: 11.5pt;
      font-weight: 700;
      color: {_DARK};
      margin-top: 22px;
      margin-bottom: 8px;
      padding-left: 10px;
      border-left: 4px solid {_AMBER};
      page-break-after: avoid;
    }}
    h3 {{
      font-size: 10.5pt;
      font-weight: 700;
      color: {_TEXT_DARK};
      margin-top: 18px;
      margin-bottom: 6px;
      page-break-after: avoid;
    }}
    h4 {{
      font-size: 10pt;
      font-weight: 700;
      color: {_TEXT_DARK};
      margin-top: 14px;
      margin-bottom: 4px;
      page-break-after: avoid;
    }}

    /* ── Body text ──────────────────────────────────────────────── */
    p {{
      margin-bottom: 8px;
      text-align: justify;
    }}
    p.spacer {{
      margin-bottom: 4px;
    }}

    /* ── Blockquote (disclaimer) ────────────────────────────────── */
    blockquote.disclaimer {{
      background: #FFF8E6;
      border-left: 4px solid #F59E0B;
      border-radius: 4px;
      padding: 12px 16px;
      margin: 16px 0;
    }}
    blockquote.disclaimer p {{
      font-size: 9pt;
      color: #92400E;
      margin: 0;
    }}

    /* ── Lists ──────────────────────────────────────────────────── */
    ul.report-list {{
      margin: 6px 0 12px 20px;
      padding: 0;
    }}
    ul.report-list li {{
      margin-bottom: 4px;
      line-height: 1.6;
    }}

    /* ── Reference links ────────────────────────────────────────── */
    a.ref-link {{
      color: {_ORANGE};
      font-size: 8.5pt;
      word-break: break-all;
      text-decoration: none;
    }}

    /* ── Tables ─────────────────────────────────────────────────── */
    table.data-table {{
      border-collapse: collapse;
      width: 100%;
      margin: 12px 0;
      font-size: 9pt;
    }}
    table.data-table th {{
      background: {_DARK};
      color: #ffffff;
      padding: 8px 12px;
      text-align: left;
      font-weight: 600;
    }}
    table.data-table td {{
      padding: 7px 12px;
      border-bottom: 1px solid {_BORDER};
      color: {_TEXT_BODY};
    }}
    table.data-table tr:nth-child(even) td {{
      background: {_CREAM};
    }}

    /* ── Inline code ─────────────────────────────────────────────── */
    code.inline-code {{
      background: {_CREAM};
      border: 1px solid {_BORDER};
      border-radius: 3px;
      padding: 1px 5px;
      font-size: 9pt;
      font-family: 'Consolas', 'Courier New', monospace;
    }}

    /* ── Strong / Em ─────────────────────────────────────────────── */
    strong {{
      color: {_TEXT_DARK};
      font-weight: 700;
    }}
"""
