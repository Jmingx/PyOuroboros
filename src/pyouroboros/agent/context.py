"""Per-session service context and Agent lifecycle owner.

AgentContext is the Session-level manager: it owns the Agent, which owns the
active AgentLoop/Run. Transports talk only to AgentContext.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pyouroboros.agent.errors import NoActiveRunError, RunBusyError
from pyouroboros.agent.settings import AgentSettings
from pyouroboros.core.approval import ApprovalService
from pyouroboros.core.events import EventBus
from pyouroboros.core.hooks import HookBus
from pyouroboros.core.ids import RunId
from pyouroboros.core.messages import Message
from pyouroboros.core.outcomes import OutcomeResolver
from pyouroboros.core.session import Session
from pyouroboros.plugins.manager import PluginSession
from pyouroboros.providers.base import ModelProvider
from pyouroboros.tools.manager import ToolManager

if TYPE_CHECKING:
    from pyouroboros.agent.agent import Agent


@dataclass(slots=True)
class AgentContext:
    session: Session
    provider: ModelProvider
    tools: ToolManager
    events: EventBus
    hooks: HookBus
    approvals: ApprovalService
    outcomes: OutcomeResolver
    settings: AgentSettings
    plugins: PluginSession | None = None
    agent: "Agent" = field(init=False)

    def __post_init__(self) -> None:
        from pyouroboros.agent.agent import Agent

        self.agent = Agent(self)

    @property
    def is_running(self) -> bool:
        return self.agent.is_running

    @property
    def run_id(self) -> RunId | None:
        return self.agent.run_id

    def start(self, message: Message) -> RunId:
        if self.agent.is_running:
            raise RunBusyError("a run is already active")
        return self.agent.start(message)

    def cancel(self) -> bool:
        return self.agent.cancel()

    def steer(self, message: Message) -> None:
        if not self.agent.is_running:
            raise NoActiveRunError("no active run")
        self.agent.steer(message)

    def follow_up(self, message: Message) -> None:
        if not self.agent.is_running:
            raise NoActiveRunError("no active run")
        self.agent.follow_up(message)

    def approve(self, request_id: str, action: str) -> bool:
        if not self.agent.is_running:
            raise NoActiveRunError("no active run")
        return self.agent.approve(request_id, action)
