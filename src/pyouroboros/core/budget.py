"""Run budgets and no-progress detection.

max_turns is a safety budget, not the definition of task completion.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

from pyouroboros.core.messages import ToolCall, ToolResult
from pyouroboros.core.types import RunStopReason


@dataclass
class RunBudget:
    max_turns: int = 50
    max_tool_calls: int | None = 100
    max_seconds: float | None = None
    started_at: float = field(default_factory=time.monotonic)
    turns: int = 0
    tool_calls: int = 0

    def begin_turn(self) -> RunStopReason | None:
        if self.turns >= self.max_turns:
            return RunStopReason.MAX_TURNS
        if self.max_seconds is not None and self.elapsed_seconds >= self.max_seconds:
            return RunStopReason.BUDGET_EXHAUSTED
        self.turns += 1
        return None

    def record_tool_calls(self, count: int) -> RunStopReason | None:
        self.tool_calls += count
        if self.max_tool_calls is not None and self.tool_calls >= self.max_tool_calls:
            return RunStopReason.BUDGET_EXHAUSTED
        return None

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_at


@dataclass
class NoProgressGuard:
    repeat_limit: int = 3
    _last_signature: str | None = None
    _repeats: int = 0

    def observe(self, calls: Sequence[ToolCall], results: Sequence[ToolResult]) -> bool:
        if self.repeat_limit <= 0:
            return False
        signature = json.dumps(
            [
                {
                    "call": {
                        "name": call.name,
                        "arguments": call.arguments,
                    },
                    "result": {
                        "ok": result.ok,
                        "content": result.content,
                        "error": result.error,
                    },
                }
                for call, result in zip(calls, results, strict=False)
            ],
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        if signature == self._last_signature:
            self._repeats += 1
        else:
            self._last_signature = signature
            self._repeats = 1
        return self._repeats >= self.repeat_limit
