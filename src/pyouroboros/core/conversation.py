"""Run-scoped conversation projection and message queues.

The loop reads/writes through this object; it never mutates Session or queue
internals directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pyouroboros.core.history import build_initial_messages, validate_history
from pyouroboros.core.messages import Message, ToolResult, tool_message
from pyouroboros.core.queues import MessageQueue
from pyouroboros.core.session import Session
from pyouroboros.core.types import QueueMode


class MessageSource(Protocol):
    def snapshot(self) -> tuple[Message, ...]: ...
    def drain_steering(self) -> tuple[Message, ...]: ...
    def drain_follow_up(self) -> tuple[Message, ...]: ...
    def append_assistant(self, message: Message) -> None: ...
    def append_tool_results(self, results: Sequence[ToolResult]) -> None: ...
    def has_pending_input(self) -> bool: ...


class Conversation:
    """Provider messages + queues for one Run, backed by a Session."""

    def __init__(
        self,
        session: Session,
        system_prompt: str,
        steering_mode: QueueMode = QueueMode.ONE_AT_A_TIME,
        follow_up_mode: QueueMode = QueueMode.ONE_AT_A_TIME,
    ) -> None:
        self.session = session
        self.system_prompt = system_prompt
        self.steer_queue = MessageQueue(steering_mode)
        self.follow_up_queue = MessageQueue(follow_up_mode)
        self._messages: list[Message] = []

    def bootstrap(self, user_input: Message) -> None:
        messages = build_initial_messages(
            self.system_prompt,
            self.session.history(),
            user_input,
        )
        self.session.append(user_input)
        self._messages = list(messages)

    def snapshot(self) -> tuple[Message, ...]:
        return tuple(self._messages)

    def drain_steering(self) -> tuple[Message, ...]:
        messages = self.steer_queue.drain()
        self._append_and_validate(messages)
        return messages

    def drain_follow_up(self) -> tuple[Message, ...]:
        messages = self.follow_up_queue.drain()
        self._append_and_validate(messages)
        return messages

    def append_assistant(self, message: Message) -> None:
        # An assistant tool-call message is intentionally incomplete until its
        # tool results are appended; validate at the next model boundary.
        self._append((message,))

    def append_tool_results(self, results: Sequence[ToolResult]) -> None:
        self._append_and_validate(tuple(tool_message(result) for result in results))

    def _append(self, messages: Sequence[Message]) -> None:
        for message in messages:
            self._messages.append(message)
            self.session.append(message)

    def _append_and_validate(self, messages: Sequence[Message]) -> None:
        self._append(messages)
        validate_history(self._messages)

    def steer(self, message: Message) -> None:
        self.steer_queue.enqueue(message)

    def follow_up(self, message: Message) -> None:
        self.follow_up_queue.enqueue(message)

    def has_pending_input(self) -> bool:
        return self.steer_queue.has_items() or self.follow_up_queue.has_items()
