"""Agent: session-scoped execution facade.

Agent owns the active AgentLoop only. AgentLoop owns its Run. AgentContext
owns the Agent and is the transport-facing session manager.
"""

from __future__ import annotations

import asyncio

from pyouroboros.agent.context import AgentContext
from pyouroboros.agent.errors import NoActiveRunError, RunBusyError
from pyouroboros.agent.loop import AgentLoop
from pyouroboros.agent.tool_executor import ToolExecutor
from pyouroboros.core.approval import ApprovalService
from pyouroboros.core.ids import RunId
from pyouroboros.core.messages import Message
from pyouroboros.core.types import ApprovalAction, RunResult


class Agent:
    def __init__(self, context: AgentContext) -> None:
        self.context = context
        self.executor = ToolExecutor(context)
        self._task: asyncio.Task[RunResult] | None = None
        self._loop: AgentLoop | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def run_id(self) -> RunId | None:
        return self._loop.run.id if self._loop is not None else None

    @property
    def approvals(self) -> ApprovalService:
        return self.context.approvals

    def start(self, message: Message) -> RunId:
        if self.is_running:
            raise RunBusyError("a run is already active")
        loop = AgentLoop(
            self.context,
            self.executor,
            self.context.settings,
            message,
        )
        self._loop = loop
        self._task = asyncio.create_task(loop.execute())
        self._task.add_done_callback(self._clear)
        return loop.run.id

    async def wait(self) -> RunResult:
        if self._task is None:
            raise NoActiveRunError("no active run")
        return await self._task

    def cancel(self) -> bool:
        if self._loop is None:
            return False
        self.context.approvals.cancel_all()
        self._loop.run.cancel()
        if self._task is not None and not self._task.done():
            self._task.cancel()
        return True

    def steer(self, message: Message) -> None:
        if self._loop is None:
            raise NoActiveRunError("no active run")
        self._loop.run.steer(message)

    def follow_up(self, message: Message) -> None:
        if self._loop is None:
            raise NoActiveRunError("no active run")
        self._loop.run.follow_up(message)

    def approve(self, request_id: str, action: str) -> bool:
        if self._loop is None:
            raise NoActiveRunError("no active run")
        mapped = ApprovalAction.ALLOW if action == "allow" else ApprovalAction.DENY
        return self.context.approvals.resolve(request_id, mapped, "user decision")

    def _clear(self, task: asyncio.Task[RunResult]) -> None:
        if self._task is task:
            self._task = None
            self._loop = None
