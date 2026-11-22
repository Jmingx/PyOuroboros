from __future__ import annotations

from pyouroboros.core.hooks import ToolAction, ToolCallRequest
from pyouroboros.core.ids import ToolCallId
from pyouroboros.core.messages import ToolCall
from pyouroboros.core.policy import (
    PolicyAction,
    PolicyEngine,
    PolicyMode,
    PolicyRule,
)
from pyouroboros.core.types import ToolSchema, ToolSpec


def spec(
    name: str = "write_note",
    side_effect: str = "write",
    requires_approval: bool = False,
) -> ToolSpec:
    return ToolSpec(
        schema=ToolSchema(
            name=name,
            description=name,
            parameters={"type": "object", "properties": {}},
        ),
        side_effect=side_effect,  # type: ignore[arg-type]
        requires_approval=requires_approval,
    )


def request(tool: ToolSpec, **arguments: object) -> ToolCallRequest:
    return ToolCallRequest(
        tool=tool,
        call=ToolCall(
            id=ToolCallId("call_1"),
            name=tool.name,
            arguments=arguments,
        ),
    )


def test_auto_mode_read_allow_write_ask() -> None:
    engine = PolicyEngine(mode=PolicyMode.AUTO)
    assert engine.decide(request(spec("read", "read"))).action is PolicyAction.ALLOW
    assert engine.decide(request(spec("write_note", "write"))).action is PolicyAction.ASK


def test_bypass_mode_allows() -> None:
    engine = PolicyEngine(mode=PolicyMode.BYPASS)
    assert engine.decide(request(spec())).action is PolicyAction.ALLOW


def test_readonly_mode_denies_writes() -> None:
    engine = PolicyEngine(mode=PolicyMode.READONLY)
    assert engine.decide(request(spec())).action is PolicyAction.DENY


def test_deny_rule_beats_bypass() -> None:
    engine = PolicyEngine(
        mode=PolicyMode.BYPASS,
        rules=(
            PolicyRule(
                id="deny-secrets",
                action=PolicyAction.DENY,
                path_glob="**/.env*",
                priority=1000,
            ),
        ),
    )
    assert (
        engine.decide(request(spec("read_file", "read"), path=".env")).action
        is PolicyAction.DENY
    )


def test_tool_specific_ask_rule() -> None:
    engine = PolicyEngine(
        mode=PolicyMode.BYPASS,
        rules=(
            PolicyRule(
                id="ask-write-note",
                action=PolicyAction.ASK,
                tool="write_note",
                reason="notes need approval",
            ),
        ),
    )
    decision = engine.decide(request(spec("write_note", "write")))
    assert decision.action is PolicyAction.ASK
    assert decision.rule_id == "ask-write-note"


def test_policy_guard_maps_actions() -> None:
    from pyouroboros.plugins.builtin.policy.guard import PolicyGuard

    guard = PolicyGuard(PolicyEngine(mode=PolicyMode.AUTO))
    decision = guard(request(spec("write_note", "write")))
    assert decision.action is ToolAction.ASK
    assert decision.reason
