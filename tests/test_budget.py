from __future__ import annotations

from pyouroboros.core.budget import NoProgressGuard, RunBudget
from pyouroboros.core.ids import ToolCallId
from pyouroboros.core.messages import ToolCall, ToolResult
from pyouroboros.core.types import RunStopReason


def test_turn_budget_is_safety_limit() -> None:
    budget = RunBudget(max_turns=2)
    assert budget.begin_turn() is None
    assert budget.begin_turn() is None
    assert budget.begin_turn() is RunStopReason.MAX_TURNS


def test_tool_call_budget() -> None:
    budget = RunBudget(max_turns=10, max_tool_calls=2)
    assert budget.record_tool_calls(1) is None
    assert budget.record_tool_calls(1) is RunStopReason.BUDGET_EXHAUSTED


def test_no_progress_guard_detects_repeated_batch() -> None:
    guard = NoProgressGuard(repeat_limit=3)
    call = ToolCall(id=ToolCallId("c1"), name="echo", arguments={"text": "x"})
    result = ToolResult(call_id=call.id, ok=True, content="x")

    assert guard.observe((call,), (result,)) is False
    assert guard.observe((call,), (result,)) is False
    assert guard.observe((call,), (result,)) is True


def test_no_progress_guard_resets_on_new_batch() -> None:
    guard = NoProgressGuard(repeat_limit=2)
    call = ToolCall(id=ToolCallId("c1"), name="echo", arguments={"text": "x"})
    other = ToolCall(id=ToolCallId("c2"), name="echo", arguments={"text": "y"})
    result = ToolResult(call_id=call.id, ok=True, content="x")
    other_result = ToolResult(call_id=other.id, ok=True, content="y")

    assert guard.observe((call,), (result,)) is False
    assert guard.observe((other,), (other_result,)) is False
    assert guard.observe((other,), (other_result,)) is True
