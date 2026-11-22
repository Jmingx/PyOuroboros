"""The loop algorithm only.

Messages, queues, and session writes go through Conversation (via config);
stop reasons go through OutcomeResolver; tools go through ToolExecutor.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import replace

from pyouroboros.agent.context import AgentContext
from pyouroboros.agent.settings import AgentSettings
from pyouroboros.agent.tool_executor import ToolExecutor
from pyouroboros.core.events import (
    ModelDelta,
    ModelFinished,
    RunFinished,
    RunStarted,
    TurnStarted,
)
from pyouroboros.core.history import HistoryIntegrityError, validate_history
from pyouroboros.core.hooks import HookError, HookPhase
from pyouroboros.core.ids import RunId
from pyouroboros.core.messages import Message, ToolResult
from pyouroboros.core.outcomes import OutcomeKind
from pyouroboros.core.run import Run
from pyouroboros.core.types import (
    ModelCall,
    RunResult,
    RunStatus,
    RunStopReason,
    Usage,
)


class AgentLoop:
    def __init__(
        self,
        context: AgentContext,
        executor: ToolExecutor,
        settings: AgentSettings,
        message: Message,
    ) -> None:
        self.context = context
        self.executor = executor
        self.message = message
        self.run = Run(
            id=RunId(uuid.uuid4().hex),
            config=settings.to_loop_config(),
            session=context.session,
        )

    async def execute(self) -> RunResult:
        run = self.run
        run.config = replace(run.config, message_source=run.conversation)
        try:
            run.conversation.bootstrap(self.message)
        except HistoryIntegrityError as exc:
            result = self._failed(run, RunStopReason.PROTOCOL_ERROR, str(exc))
            await self.context.events.emit(RunFinished(result=result))
            return result

        await self.context.events.emit(
            RunStarted(
                run_id=run.id,
                session_id=self.context.session.id,
                input=self.message,
            )
        )
        result = await self._execute_loop()
        await self.context.events.emit(RunFinished(result=result))
        return result

    async def _execute_loop(self) -> RunResult:
        run = self.run
        try:
            return await self._loop(run)
        except asyncio.CancelledError:
            run.status = RunStatus.CANCELLED
            return RunResult(
                run_id=run.id,
                status=RunStatus.CANCELLED,
                usage=run.usage,
                stop_reason=RunStopReason.CANCELLED,
            )
        except HistoryIntegrityError as exc:
            return self._failed(run, RunStopReason.PROTOCOL_ERROR, str(exc))
        except HookError as exc:
            return self._failed(run, RunStopReason.ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001 - terminal boundary
            return self._failed(run, RunStopReason.ERROR, str(exc))

    async def _loop(self, run: Run) -> RunResult:
        source = run.config.message_source
        if source is None:
            raise RuntimeError("AgentLoopConfig.message_source is required")

        while True:
            budget_reason = run.budget.begin_turn()
            if budget_reason is not None:
                error = (
                    "turn budget exhausted"
                    if budget_reason is RunStopReason.MAX_TURNS
                    else "run budget exhausted"
                )
                return self._failed(run, budget_reason, error)

            run.turn = run.budget.turns
            source.drain_steering()
            await self.context.events.emit(TurnStarted(run_id=run.id, turn=run.turn))

            call = ModelCall(
                messages=source.snapshot(),
                tools=self.context.tools.specs(),
                model=run.config.model,
            )
            call = await self.context.hooks.transform(
                HookPhase.BEFORE_MODEL_CALL,
                call,
                ModelCall,
            )
            validate_history(call.messages)

            async def on_delta(text: str) -> None:
                await self.context.events.emit(ModelDelta(run_id=run.id, text=text))

            response = await self.context.provider.stream(
                call,
                on_delta,
                run.cancel_event,
            )
            response = await self.context.hooks.transform(
                HookPhase.AFTER_MODEL_CALL,
                response,
                type(response),
            )
            run.usage = Usage(
                prompt_tokens=run.usage.prompt_tokens + response.usage.prompt_tokens,
                completion_tokens=run.usage.completion_tokens + response.usage.completion_tokens,
            )
            await self.context.events.emit(
                ModelFinished(
                    run_id=run.id,
                    content=response.message.text,
                    stop_reason=response.stop_reason,
                    usage=response.usage,
                )
            )
            source.append_assistant(response.message)

            outcome = self.context.outcomes.resolve(response)
            if outcome.kind is OutcomeKind.FAILED:
                failed = [
                    ToolResult(
                        call_id=call.id,
                        ok=False,
                        content="",
                        error=outcome.error or "model response was not executable",
                    )
                    for call in response.message.tool_calls
                ]
                source.append_tool_results(failed)
                return self._failed(
                    run,
                    outcome.stop_reason or RunStopReason.ERROR,
                    outcome.error or "model response failed",
                    output=response.message,
                )

            if outcome.kind is OutcomeKind.FINAL:
                source.drain_follow_up()
                if source.has_pending_input():
                    continue
                if run.complete_if_idle():
                    return RunResult(
                        run_id=run.id,
                        status=RunStatus.COMPLETED,
                        output=response.message,
                        usage=run.usage,
                        stop_reason=RunStopReason.FINAL_ANSWER,
                    )
                continue

            results = await self.executor.execute_batch(run, response.message.tool_calls)
            source.append_tool_results(results)
            tool_budget = run.budget.record_tool_calls(len(results))
            if tool_budget is not None:
                return self._failed(run, tool_budget, "tool-call budget exhausted")
            if run.guard.observe(response.message.tool_calls, results):
                return self._failed(run, RunStopReason.NO_PROGRESS, "no progress detected")
            if run.cancel_event.is_set():
                raise asyncio.CancelledError

    @staticmethod
    def _failed(
        run: Run,
        reason: RunStopReason,
        error: str,
        output: Message | None = None,
    ) -> RunResult:
        run.status = RunStatus.FAILED
        return RunResult(
            run_id=run.id,
            status=RunStatus.FAILED,
            output=output,
            usage=run.usage,
            error=error,
            stop_reason=reason,
        )
