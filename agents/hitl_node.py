from __future__ import annotations

from schemas.state import WorkflowState


class HitlNode:
    """HITL 노드는 현재 구현에서는 진행 승인 여부만 명시적으로 기록한다."""

    def review(self, state: WorkflowState) -> bool:
        # 실제 서비스에서는 담당자 UI 입력을 받아야 한다.
        # 현재 골격은 설계 흐름 검증 목적이므로 기본 승인으로 처리한다.
        return True
