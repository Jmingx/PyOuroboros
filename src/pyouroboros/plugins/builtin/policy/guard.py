"""Policy decision -> BeforeToolCall guard."""

from __future__ import annotations

from pyouroboros.core.hooks import ToolAction, ToolCallRequest, ToolGuardDecision
from pyouroboros.core.policy import PolicyAction, PolicyDecision, PolicyEngine


class PolicyGuard:
    def __init__(self, engine: PolicyEngine) -> None:
        self.engine = engine

    def __call__(self, request: ToolCallRequest) -> ToolGuardDecision:
        decision = self.engine.decide(request)
        return ToolGuardDecision(
            action=self._to_tool_action(decision),
            reason=decision.reason,
            rule_id=decision.rule_id,
            scope=decision.scope,
        )

    @staticmethod
    def _to_tool_action(decision: PolicyDecision) -> ToolAction:
        if decision.action is PolicyAction.ALLOW:
            return ToolAction.ALLOW
        if decision.action is PolicyAction.DENY:
            return ToolAction.DENY
        return ToolAction.ASK
