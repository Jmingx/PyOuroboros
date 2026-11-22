"""Provider-message projection and integrity checks."""

from __future__ import annotations

from collections.abc import Sequence

from pyouroboros.core.messages import Message, system_message


class HistoryIntegrityError(ValueError):
    """The conversation cannot be safely converted into provider messages."""


def validate_history(messages: Sequence[Message]) -> None:
    """Validate the invariants required by OpenAI-style tool calling.

    Rules:
    - system messages may appear only at index 0;
    - every tool call id is unique;
    - every tool call must be followed by exactly one matching tool result;
    - no user/assistant message may interleave before a tool batch is complete;
    - tool results may not appear without a pending call;
    - assistant messages must contain text or tool calls.
    """

    pending: dict[str, str] = {}
    seen_calls: set[str] = set()

    for index, message in enumerate(messages):
        if message.role == "system":
            if index != 0:
                raise HistoryIntegrityError("system message must be first")
            continue

        if message.role == "tool":
            result = message.tool_result
            if result is None:
                raise HistoryIntegrityError("tool message missing ToolResult block")
            if result.call_id not in pending:
                raise HistoryIntegrityError(
                    f"tool result {result.call_id!r} has no pending tool call"
                )
            pending.pop(result.call_id)
            continue

        if pending:
            raise HistoryIntegrityError(
                f"{message.role} message appeared before tool batch completed"
            )

        if message.role == "assistant":
            calls = message.tool_calls
            if not message.text and not calls:
                raise HistoryIntegrityError("empty assistant message")
            for call in calls:
                if call.id in seen_calls:
                    raise HistoryIntegrityError(f"duplicate tool call id {call.id!r}")
                seen_calls.add(call.id)
                pending[call.id] = call.name
            continue

        if message.role not in ("user", "assistant"):
            raise HistoryIntegrityError(f"unsupported role {message.role!r}")

    if pending:
        raise HistoryIntegrityError(
            "unresolved tool calls: " + ", ".join(sorted(pending))
        )


def build_initial_messages(
    system_prompt: str,
    history: Sequence[Message],
    user_input: Message,
) -> tuple[Message, ...]:
    messages = (system_message(system_prompt), *history, user_input)
    validate_history(messages)
    return messages
