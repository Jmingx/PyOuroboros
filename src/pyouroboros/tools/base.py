"""Tool value objects and execution boundary."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from pyouroboros.core.ids import SessionId
from pyouroboros.core.messages import ToolCall, ToolResult
from pyouroboros.core.types import ToolSpec


@dataclass(frozen=True, slots=True)
class ToolContext:
    session_id: SessionId
    workspace: Path


ToolHandler = Callable[[ToolCall, ToolContext], Awaitable[ToolResult] | ToolResult]


@dataclass(frozen=True, slots=True)
class Tool:
    spec: ToolSpec
    handler: ToolHandler

    async def execute(self, call: ToolCall, context: ToolContext) -> ToolResult:
        try:
            if inspect.iscoroutinefunction(self.handler):
                result = await self.handler(call, context)
            else:
                result = await asyncio.to_thread(self.handler, call, context)
            if not isinstance(result, ToolResult):
                raise TypeError(f"tool {self.spec.name!r} returned {type(result).__name__}")
            return result
        except Exception as exc:  # noqa: BLE001 - tool failures are model-visible
            return ToolResult(call_id=call.id, ok=False, content="", error=str(exc))
