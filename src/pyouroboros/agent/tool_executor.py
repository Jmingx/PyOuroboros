"""Tool batch execution: hooks + approval + registry, outside the loop."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from pyouroboros.agent.context import AgentContext
from pyouroboros.core.events import ToolFinished, ToolStarted
from pyouroboros.core.hooks import (
    HookPhase,
    ToolAction,
    ToolCallRequest,
    ToolGuardDecision,
)
from pyouroboros.core.ids import ApprovalId
from pyouroboros.core.messages import ToolCall, ToolResult
from pyouroboros.core.run import Run
from pyouroboros.core.types import ApprovalAction, ApprovalRequest, ToolExecutionMode
from pyouroboros.tools.base import Tool, ToolContext


@dataclass(frozen=True, slots=True)
class PreparedCall:
    call: ToolCall
    tool: Tool | None
    decision: ToolGuardDecision


class ToolExecutor:
    def __init__(self, context: AgentContext) -> None:
        self.context = context

    async def execute_batch(self, run: Run, calls: tuple[ToolCall, ...]) -> list[ToolResult]:
        # Guards are evaluated first and always in source order.
        prepared = [await self._prepare(call) for call in calls]

        can_parallel = (
            run.config.tool_execution is ToolExecutionMode.PARALLEL
            and len(prepared) > 1
            and all(item.decision.action is ToolAction.ALLOW for item in prepared)
        )
        if can_parallel:
            return list(
                await asyncio.gather(
                    *(self._execute_prepared(run, item) for item in prepared)
                )
            )

        results: list[ToolResult] = []
        for item in prepared:
            results.append(await self._execute_prepared(run, item))
        return results

    async def _prepare(self, call: ToolCall) -> PreparedCall:
        tool = self.context.tools.get(call.name)
        if tool is None:
            return PreparedCall(
                call=call,
                tool=None,
                decision=ToolGuardDecision(
                    action=ToolAction.DENY,
                    reason=f"unknown tool: {call.name}",
                ),
            )
        decision = await self.context.hooks.guard(
            HookPhase.BEFORE_TOOL_CALL,
            ToolCallRequest(tool=tool.spec, call=call),
        )
        return PreparedCall(call=call, tool=tool, decision=decision)

    async def _execute_prepared(self, run: Run, prepared: PreparedCall) -> ToolResult:
        call = prepared.call
        if prepared.tool is None:
            result = ToolResult(
                call_id=call.id,
                ok=False,
                content="",
                error=prepared.decision.reason,
            )
            await self.context.events.emit(
                ToolFinished(run_id=run.id, call=call, result=result)
            )
            return result

        if prepared.decision.action is ToolAction.DENY:
            result = ToolResult(
                call_id=call.id,
                ok=False,
                content="",
                error=prepared.decision.reason or "denied by hook",
            )
            await self.context.events.emit(
                ToolFinished(run_id=run.id, call=call, result=result)
            )
            return result

        if prepared.decision.action is ToolAction.ASK:
            request = ApprovalRequest(
                id=ApprovalId(f"approval_{uuid.uuid4().hex[:8]}"),
                run_id=run.id,
                tool_call=call,
                reason=prepared.decision.reason,
            )
            decision = await self.context.approvals.request(request, self.context.events)
            if decision.action is not ApprovalAction.ALLOW:
                result = ToolResult(
                    call_id=call.id,
                    ok=False,
                    content="",
                    error=f"approval {decision.action.value}: {decision.reason}",
                )
                await self.context.events.emit(
                    ToolFinished(run_id=run.id, call=call, result=result)
                )
                return result

        await self.context.events.emit(ToolStarted(run_id=run.id, call=call))
        result = await prepared.tool.execute(
            call,
            ToolContext(session_id=run.session.id, workspace=run.session.workspace),
        )
        result = await self.context.hooks.transform(
            HookPhase.AFTER_TOOL_CALL,
            result,
            ToolResult,
        )
        await self.context.events.emit(
            ToolFinished(run_id=run.id, call=call, result=result)
        )
        return result
