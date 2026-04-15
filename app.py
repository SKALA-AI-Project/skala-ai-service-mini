from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflows.report_workflow import run_report_workflow


def parse_args() -> argparse.Namespace:
    """CLI 실행에 필요한 최소 인자를 정의한다."""
    parser = argparse.ArgumentParser(
        description="기술 전략 분석 보고서 Agentic Workflow 실행기"
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/reports",
        help="보고서 산출물을 저장할 디렉토리",
    )
    parser.add_argument(
        "--save-state",
        action="store_true",
        help="최종 상태 JSON을 함께 저장할지 여부",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="실제 API 대신 mock 경로로 실행할지 여부",
    )
    parser.add_argument(
        "--query",
        default="",
        help="Supervisor가 분석 범위를 추출할 사용자 요청 문장",
    )
    parser.add_argument(
        "--writer",
        nargs="+",
        metavar="NAME",
        default=[],
        help="작성자 이름 (예: --writer 김세림 남희정 최지호)",
    )
    return parser.parse_args()


def main() -> None:
    """워크플로우를 실행하고 주요 산출물 경로를 출력한다."""
    args = parse_args()
    print(
        "[LOG] CLI 실행:"
        f" output_dir={args.output_dir}, mock={args.mock},"
        f" save_state={args.save_state}, query={'있음' if args.query else '없음'}"
    )
    final_state = run_report_workflow(
        output_dir=Path(args.output_dir),
        user_query=args.query,
        use_live_api=not args.mock,
        writers=args.writer or None,
    )

    print("워크플로우 실행 완료")
    print(f"- Markdown: {final_state['final_report_md_path']}")
    print(f"- PDF: {final_state['final_report_pdf_path']}")

    if args.save_state:
        state_path = Path(args.output_dir) / "final_state.json"
        state_path.write_text(
            json.dumps(final_state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[LOG] 상태 JSON 저장 완료: {state_path}")
        print(f"- 상태 JSON: {state_path}")


if __name__ == "__main__":
    main()
