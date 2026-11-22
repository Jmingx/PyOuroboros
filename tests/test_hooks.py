from __future__ import annotations

import pytest

from pyouroboros.core.hooks import (
    HookBus,
    HookPhase,
    ToolAction,
    ToolCallRequest,
)
from pyouroboros.core.ids import ToolCallId
from pyouroboros.core.messages import ToolCall
from pyouroboros.core.policy import PolicyEngine, PolicyMode
from pyouroboros.core.types import ToolSchema, ToolSpec
from pyouroboros.plugins.builtin.policy.guard import PolicyGuard


def write_tool_spec() -> ToolSpec:
    return ToolSpec(
        schema=ToolSchema(
            name="write_note",
            description="write",
            parameters={"type": "object", "properties": {}},
        ),
        side_effect="write",
        requires_approval=True,
    )


def read_tool_spec() -> ToolSpec:
    return ToolSpec(
        schema=ToolSchema(
            name="get_time",
            description="time",
            parameters={"type": "object", "properties": {}},
        ),
        side_effect="read",
    )


def call() -> ToolCall:
    return ToolCall(id=ToolCallId("call_1"), name="write_note", arguments={})


@pytest.mark.asyncio
async def test_transform_order_and_type() -> None:
    bus = HookBus()

    def second(value: int) -> int:
        return value * 10

    def first(value: int) -> int:
        return value + 1

    bus.register(HookPhase.BEFORE_MODEL_CALL, second, priority=20)
    bus.register(HookPhase.BEFORE_MODEL_CALL, first, priority=10)

    assert await bus.transform(HookPhase.BEFORE_MODEL_CALL, 1, int) == 20


@pytest.mark.asyncio
async def test_approval_hook_asks_for_write_tool() -> None:
    bus = HookBus()
    bus.register(
        HookPhase.BEFORE_TOOL_CALL,
        PolicyGuard(PolicyEngine(mode=PolicyMode.AUTO)),
        priority=10,
    )

    decision = await bus.guard(
        HookPhase.BEFORE_TOOL_CALL,
        ToolCallRequest(tool=write_tool_spec(), call=call()),
    )
    assert decision.action is ToolAction.ASK

    decision = await bus.guard(
        HookPhase.BEFORE_TOOL_CALL,
        ToolCallRequest(tool=read_tool_spec(), call=call()),
    )
    assert decision.action is ToolAction.ALLOW
