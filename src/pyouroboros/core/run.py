"""Run state: budgets, conversation projection, and queues."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from pyouroboros.core.budget import NoProgressGuard, RunBudget
from pyouroboros.core.conversation import Conversation
from pyouroboros.core.ids import RunId
from pyouroboros.core.messages import Message
from pyouroboros.core.queues import MessageQueue
from pyouroboros.core.session import Session
from pyouroboros.core.types import AgentLoopConfig, RunStatus, Usage


class RunClosedError(RuntimeError):
    """Raised when steering/follow-up targets a terminal Run."""


@dataclass
class Run:
    id: RunId
    config: AgentLoopConfig
    session: Session
    status: RunStatus = RunStatus.RUNNING
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    usage: Usage = field(default_factory=Usage)
    output: Message | None = None
    turn: int = 0
    conversation: Conversation = field(init=False)
    budget: RunBudget = field(init=False)
    guard: NoProgressGuard = field(init=False)

    def __post_init__(self) -> None:
        self.conversation = Conversation(
            session=self.session,
            system_prompt=self.config.system_prompt,
            steering_mode=self.config.steering_mode,
            follow_up_mode=self.config.follow_up_mode,
        )
        self.budget = RunBudget(
            max_turns=self.config.max_turns,
            max_tool_calls=self.config.max_tool_calls,
            max_seconds=self.config.max_seconds,
        )
        self.guard = NoProgressGuard(self.config.no_progress_repeat_limit)

    @property
    def is_active(self) -> bool:
        return self.status in (RunStatus.PENDING, RunStatus.RUNNING, RunStatus.CANCELLING)

    @property
    def steer_queue(self) -> MessageQueue:
        return self.conversation.steer_queue

    @property
    def follow_up_queue(self) -> MessageQueue:
        return self.conversation.follow_up_queue

    def steer(self, message: Message) -> None:
        if not self.is_active:
            raise RunClosedError(f"run {self.id} is {self.status.value}")
        self.conversation.steer(message)

    def follow_up(self, message: Message) -> None:
        if not self.is_active:
            raise RunClosedError(f"run {self.id} is {self.status.value}")
        self.conversation.follow_up(message)

    def cancel(self) -> None:
        self.cancel_event.set()
        if self.status is RunStatus.RUNNING:
            self.status = RunStatus.CANCELLING

    def complete_if_idle(self) -> bool:
        """Atomically become COMPLETED only when no queued input remains."""
        if self.status is not RunStatus.RUNNING:
            return False
        if self.conversation.has_pending_input():
            return False
        self.status = RunStatus.COMPLETED
        return True
