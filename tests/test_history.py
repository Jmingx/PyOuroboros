from __future__ import annotations

import pytest

from pyouroboros.core.history import HistoryIntegrityError, build_initial_messages
from pyouroboros.core.ids import ToolCallId
from pyouroboros.core.messages import (
    ToolCall,
    ToolResult,
    assistant_message,
    tool_message,
    user_message,
)


def test_valid_tool_pair() -> None:
    call = ToolCall(id=ToolCallId("c1"), name="echo", arguments={"text": "x"})
    messages = build_initial_messages(
        "system",
        [
            assistant_message("", (call,)),
            tool_message(ToolResult(call_id=call.id, ok=True, content="x")),
        ],
        user_message("next"),
    )
    assert len(messages) == 4


def test_orphan_tool_call_rejected() -> None:
    call = ToolCall(id=ToolCallId("c1"), name="echo", arguments={})
    with pytest.raises(HistoryIntegrityError):
        build_initial_messages(
            "system",
            [assistant_message("", (call,))],
            user_message("next"),
        )


def test_orphan_tool_result_rejected() -> None:
    with pytest.raises(HistoryIntegrityError):
        build_initial_messages(
            "system",
            [tool_message(ToolResult(call_id=ToolCallId("c1"), ok=True, content="x"))],
            user_message("next"),
        )
