"""Minimal async event bus and typed event payloads."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pyouroboros.core.ids import RunId
from pyouroboros.core.messages import Message, ToolCall, ToolResult
from pyouroboros.core.types import (
    ApprovalDecision,
    ApprovalRequest,
    ModelStopReason,
    RunResult,
    Usage,
)


@dataclass(frozen=True, slots=True)
class RunStarted:
    run_id: RunId
    session_id: str
    input: Message


@dataclass(frozen=True, slots=True)
class TurnStarted:
    run_id: RunId
    turn: int


@dataclass(frozen=True, slots=True)
class ModelDelta:
    run_id: RunId
    text: str


@dataclass(frozen=True, slots=True)
class ModelFinished:
    run_id: RunId
    content: str
    stop_reason: ModelStopReason
    usage: Usage


@dataclass(frozen=True, slots=True)
class ToolStarted:
    run_id: RunId
    call: ToolCall


@dataclass(frozen=True, slots=True)
class ToolFinished:
    run_id: RunId
    call: ToolCall
    result: ToolResult


@dataclass(frozen=True, slots=True)
class ApprovalRequested:
    run_id: RunId
    request: ApprovalRequest


@dataclass(frozen=True, slots=True)
class ApprovalResolved:
    run_id: RunId
    decision: ApprovalDecision


@dataclass(frozen=True, slots=True)
class RunFinished:
    result: RunResult


Event = (
    RunStarted
    | TurnStarted
    | ModelDelta
    | ModelFinished
    | ToolStarted
    | ToolFinished
    | ApprovalRequested
    | ApprovalResolved
    | RunFinished
)

Handler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    """Session-scoped bus. Handler failures are logged, never break the loop."""

    def __init__(self) -> None:
        self._handlers: list[Handler] = []

    def on_any(self, handler: Handler) -> Callable[[], None]:
        self._handlers.append(handler)

        def unsubscribe() -> None:
            if handler in self._handlers:
                self._handlers.remove(handler)

        return unsubscribe

    async def emit(self, event: Event) -> None:
        for handler in tuple(self._handlers):
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:  # noqa: BLE001 - observer failures must be isolated
                await asyncio.sleep(0)
