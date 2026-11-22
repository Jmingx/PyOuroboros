"""Deterministic fake provider for tests and no-key local demos."""

from __future__ import annotations

import asyncio
import uuid

from pyouroboros.core.ids import ToolCallId
from pyouroboros.core.messages import ToolCall, assistant_message
from pyouroboros.core.types import (
    ModelCall,
    ModelResponse,
    ModelStopReason,
    Usage,
)
from pyouroboros.providers.base import DeltaHandler


class FakeProvider:
    name = "fake"

    def __init__(self, model: str = "fake-echo") -> None:
        self.model = model

    async def stream(
        self,
        call: ModelCall,
        on_delta: DeltaHandler,
        cancel_event: asyncio.Event,
    ) -> ModelResponse:
        last = call.messages[-1] if call.messages else None
        user_text = ""
        for message in reversed(call.messages):
            if message.role == "user":
                user_text = message.text
                break

        if last is not None and last.role == "tool":
            result = last.tool_result
            if result is not None and result.ok:
                text = f"Done. {result.content}"
            elif result is not None:
                text = f"The tool was not executed: {result.error or 'unknown error'}"
            else:
                text = "Done."
            await self._emit_text(text, on_delta, cancel_event)
            return ModelResponse(
                message=assistant_message(text),
                usage=Usage(prompt_tokens=16, completion_tokens=len(text) // 4),
                stop_reason=ModelStopReason.STOP,
                raw_stop_reason="stop",
            )

        lowered = user_text.lower()
        wants_note = ("note" in lowered or "笔记" in user_text) and (
            "write" in lowered or "写" in user_text
        )
        if wants_note:
            prefix = "I'll save that note, pending approval."
            await self._emit_text(prefix, on_delta, cancel_event)
            tool = ToolCall(
                id=ToolCallId(f"call_{uuid.uuid4().hex[:8]}"),
                name="write_note",
                arguments={"text": user_text},
            )
            return ModelResponse(
                message=assistant_message(prefix, (tool,)),
                usage=Usage(prompt_tokens=24, completion_tokens=12),
                stop_reason=ModelStopReason.TOOL_CALLS,
                raw_stop_reason="tool_calls",
            )

        if "time" in lowered or "几点" in user_text:
            prefix = "Let me check the clock."
            await self._emit_text(prefix, on_delta, cancel_event)
            tool = ToolCall(
                id=ToolCallId(f"call_{uuid.uuid4().hex[:8]}"),
                name="get_time",
                arguments={},
            )
            return ModelResponse(
                message=assistant_message(prefix, (tool,)),
                usage=Usage(prompt_tokens=18, completion_tokens=8),
                stop_reason=ModelStopReason.TOOL_CALLS,
                raw_stop_reason="tool_calls",
            )

        text = f"Fake echo: {user_text}" if user_text else "Fake provider ready."
        await self._emit_text(text, on_delta, cancel_event)
        return ModelResponse(
            message=assistant_message(text),
            usage=Usage(prompt_tokens=12, completion_tokens=len(text) // 4),
            stop_reason=ModelStopReason.STOP,
            raw_stop_reason="stop",
        )

    @staticmethod
    async def _emit_text(text: str, on_delta: DeltaHandler, cancel_event: asyncio.Event) -> None:
        for index in range(0, len(text), 8):
            if cancel_event.is_set():
                raise asyncio.CancelledError
            await on_delta(text[index : index + 8])
            await asyncio.sleep(0.008)
