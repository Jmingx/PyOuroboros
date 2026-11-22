from __future__ import annotations

from pyouroboros.core.messages import assistant_message
from pyouroboros.core.outcomes import OutcomeKind, OutcomeResolver
from pyouroboros.core.types import ModelResponse, ModelStopReason, RunStopReason


def test_length_is_failed_not_final() -> None:
    outcome = OutcomeResolver().resolve(
        ModelResponse(
            message=assistant_message("partial"),
            stop_reason=ModelStopReason.LENGTH,
        )
    )
    assert outcome.kind is OutcomeKind.FAILED
    assert outcome.stop_reason is RunStopReason.LENGTH


def test_tool_calls_without_calls_is_protocol_error() -> None:
    outcome = OutcomeResolver().resolve(
        ModelResponse(
            message=assistant_message(""),
            stop_reason=ModelStopReason.TOOL_CALLS,
        )
    )
    assert outcome.kind is OutcomeKind.FAILED
    assert outcome.stop_reason is RunStopReason.PROTOCOL_ERROR


def test_stop_without_calls_is_final() -> None:
    outcome = OutcomeResolver().resolve(
        ModelResponse(
            message=assistant_message("hello"),
            stop_reason=ModelStopReason.STOP,
        )
    )
    assert outcome.kind is OutcomeKind.FINAL


def test_unknown_is_failed() -> None:
    outcome = OutcomeResolver().resolve(
        ModelResponse(
            message=assistant_message("?"),
            stop_reason=ModelStopReason.UNKNOWN,
            raw_stop_reason="weird",
        )
    )
    assert outcome.kind is OutcomeKind.FAILED
    assert outcome.stop_reason is RunStopReason.PROTOCOL_ERROR
