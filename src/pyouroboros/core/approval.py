"""Approval mechanism: correlate a request with a decision.

Policy (whether approval is needed) belongs to a BeforeToolCall hook.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from pyouroboros.core.events import ApprovalRequested, ApprovalResolved, EventBus
from pyouroboros.core.ids import ApprovalId
from pyouroboros.core.types import ApprovalAction, ApprovalDecision, ApprovalRequest


class ApprovalService:
    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout
        self._pending: dict[str, asyncio.Future[ApprovalDecision]] = {}

    async def request(
        self,
        request: ApprovalRequest,
        bus: EventBus,
        announce: Callable[[], None] | None = None,
    ) -> ApprovalDecision:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[ApprovalDecision] = loop.create_future()
        self._pending[request.id] = future
        try:
            await bus.emit(ApprovalRequested(run_id=request.run_id, request=request))
            if announce is not None:
                announce()
            decision = await asyncio.wait_for(future, timeout=self.timeout)
        except TimeoutError:
            decision = ApprovalDecision(
                request_id=request.id,
                action=ApprovalAction.TIMEOUT,
                reason="approval timed out",
            )
        finally:
            self._pending.pop(request.id, None)
        await bus.emit(ApprovalResolved(run_id=request.run_id, decision=decision))
        return decision

    def resolve(self, request_id: str, action: ApprovalAction, reason: str = "") -> bool:
        future = self._pending.get(request_id)
        if future is None or future.done():
            return False
        future.set_result(
            ApprovalDecision(
                request_id=ApprovalId(request_id),
                action=action,
                reason=reason,
            )
        )
        return True

    def cancel_all(self) -> None:
        for request_id, future in tuple(self._pending.items()):
            if not future.done():
                future.set_result(
                    ApprovalDecision(
                        request_id=ApprovalId(request_id),
                        action=ApprovalAction.DENY,
                        reason="run cancelled",
                    )
                )
