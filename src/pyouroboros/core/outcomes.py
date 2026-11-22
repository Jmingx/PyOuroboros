"""Model stop-reason policy, kept out of the loop algorithm."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pyouroboros.core.types import ModelResponse, ModelStopReason, RunStopReason


class OutcomeKind(StrEnum):
    FINAL = "final"
    TOOLS = "tools"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Outcome:
    kind: OutcomeKind
    stop_reason: RunStopReason | None = None
    error: str | None = None


class OutcomeResolver:
    """Total policy for (provider stop reason, tool calls) -> next action."""

    def resolve(self, response: ModelResponse) -> Outcome:
        has_tools = bool(response.message.tool_calls)
        reason = response.stop_reason

        if reason is ModelStopReason.ERROR:
            return Outcome(OutcomeKind.FAILED, RunStopReason.ERROR, "provider returned an error")
        if reason is ModelStopReason.LENGTH:
            return Outcome(
                OutcomeKind.FAILED,
                RunStopReason.LENGTH,
                "model output was truncated (length)",
            )
        if reason is ModelStopReason.CONTENT_FILTER:
            return Outcome(
                OutcomeKind.FAILED,
                RunStopReason.CONTENT_FILTER,
                "model output was blocked by content filter",
            )
        if reason is ModelStopReason.TOOL_CALLS:
            if has_tools:
                return Outcome(OutcomeKind.TOOLS)
            return Outcome(
                OutcomeKind.FAILED,
                RunStopReason.PROTOCOL_ERROR,
                "stop_reason=tool_calls but no tool calls were returned",
            )
        if reason is ModelStopReason.STOP:
            return Outcome(OutcomeKind.TOOLS if has_tools else OutcomeKind.FINAL)
        return Outcome(
            OutcomeKind.FAILED,
            RunStopReason.PROTOCOL_ERROR,
            f"unknown model stop reason: {response.raw_stop_reason or reason.value}",
        )
