from __future__ import annotations

import sys

from schemas.state import WorkflowState


class HitlNode:
    """HITL 노드는 담당자가 검색 편향 여부를 직접 확인하고 승인·거부를 결정한다."""

    def review(self, state: WorkflowState) -> bool:
        """터미널 입력으로 담당자 판단을 받는다. y/yes면 승인, 그 외는 거부."""
        print("\n" + "=" * 60)
        print("[HITL] 검색 결과 편향 검증 실패 — 담당자 검토 필요")
        print(f"  topics: {state.get('topics', [])}")
        print(f"  competitors: {state.get('competitors', [])}")
        print(f"  quality_scores: {state.get('quality_scores', {})}")
        print("=" * 60)

        if not sys.stdin.isatty():
            # 비대화형 환경(CI, pytest, 파이프 입력)에서는 자동 승인
            print("[HITL] 비대화형 환경 — 자동 승인 처리")
            return True

        try:
            answer = input("계속 진행하시겠습니까? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("[HITL] 비대화형 환경 — 자동 승인 처리")
            return True
        return answer in ("y", "yes")
