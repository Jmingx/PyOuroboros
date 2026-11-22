"""WebSocket event encoding via an explicit registry.

Core events describe facts; this module is the transport projection.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pyouroboros.core.events import (
    ApprovalRequested,
    ApprovalResolved,
    Event,
    ModelDelta,
    ModelFinished,
    RunFinished,
    RunStarted,
    ToolFinished,
    ToolStarted,
    TurnStarted,
)

Encoder = Callable[[Any], tuple[str, dict[str, Any]]]


class EventEncoderRegistry:
    def __init__(self) -> None:
        self._encoders: dict[type[object], Encoder] = {}

    def register(self, event_type: type[object]) -> Callable[[Encoder], Encoder]:
        def decorator(encoder: Encoder) -> Encoder:
            if event_type in self._encoders:
                raise ValueError(f"duplicate encoder: {event_type.__name__}")
            self._encoders[event_type] = encoder
            return encoder

        return decorator

    def encode(self, event: Event) -> tuple[str, dict[str, Any]]:
        encoder = self._encoders.get(type(event))
        if encoder is None:
            raise TypeError(f"no encoder registered for {type(event).__name__}")
        return encoder(event)


registry = EventEncoderRegistry()


@registry.register(RunStarted)
def encode_run_started(event: RunStarted) -> tuple[str, dict[str, Any]]:
    return "run.started", {"run_id": event.run_id, "session_id": event.session_id}


@registry.register(TurnStarted)
def encode_turn_started(event: TurnStarted) -> tuple[str, dict[str, Any]]:
    return "turn.started", {"run_id": event.run_id, "turn": event.turn}


@registry.register(ModelDelta)
def encode_model_delta(event: ModelDelta) -> tuple[str, dict[str, Any]]:
    return "model.delta", {"run_id": event.run_id, "text": event.text}


@registry.register(ModelFinished)
def encode_model_finished(event: ModelFinished) -> tuple[str, dict[str, Any]]:
    return (
        "model.finished",
        {
            "run_id": event.run_id,
            "content": event.content,
            "stop_reason": event.stop_reason.value,
            "usage": {
                "prompt_tokens": event.usage.prompt_tokens,
                "completion_tokens": event.usage.completion_tokens,
            },
        },
    )


@registry.register(ToolStarted)
def encode_tool_started(event: ToolStarted) -> tuple[str, dict[str, Any]]:
    return (
        "tool.started",
        {
            "run_id": event.run_id,
            "call": {
                "id": event.call.id,
                "name": event.call.name,
                "arguments": event.call.arguments,
            },
        },
    )


@registry.register(ToolFinished)
def encode_tool_finished(event: ToolFinished) -> tuple[str, dict[str, Any]]:
    return (
        "tool.finished",
        {
            "run_id": event.run_id,
            "call_id": event.call.id,
            "name": event.call.name,
            "ok": event.result.ok,
            "content": event.result.content,
            "error": event.result.error,
        },
    )


@registry.register(ApprovalRequested)
def encode_approval_requested(event: ApprovalRequested) -> tuple[str, dict[str, Any]]:
    request = event.request
    return (
        "approval.requested",
        {
            "run_id": event.run_id,
            "request_id": request.id,
            "tool_name": request.tool_call.name,
            "tool_call_id": request.tool_call.id,
            "arguments": request.tool_call.arguments,
            "reason": request.reason,
            "options": list(request.options),
        },
    )


@registry.register(ApprovalResolved)
def encode_approval_resolved(event: ApprovalResolved) -> tuple[str, dict[str, Any]]:
    return (
        "approval.resolved",
        {
            "run_id": event.run_id,
            "request_id": event.decision.request_id,
            "action": event.decision.action.value,
            "reason": event.decision.reason,
        },
    )


@registry.register(RunFinished)
def encode_run_finished(event: RunFinished) -> tuple[str, dict[str, Any]]:
    result = event.result
    return (
        "run.finished",
        {
            "run_id": result.run_id,
            "status": result.status.value,
            "output": result.output.text if result.output else "",
            "error": result.error,
            "stop_reason": result.stop_reason.value if result.stop_reason else None,
            "usage": {
                "prompt_tokens": result.usage.prompt_tokens,
                "completion_tokens": result.usage.completion_tokens,
            },
        },
    )


def encode_event(event: Event) -> tuple[str, dict[str, Any]]:
    return registry.encode(event)
