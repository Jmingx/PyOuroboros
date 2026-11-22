"""Typed hook bus.

Events observe facts; hooks intercept and may transform or guard.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeVar

from pyouroboros.core.messages import ToolCall
from pyouroboros.core.types import ToolSpec

T = TypeVar("T")


class HookPhase(StrEnum):
    BEFORE_MODEL_CALL = "before_model_call"
    AFTER_MODEL_CALL = "after_model_call"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"


class ToolAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass(frozen=True, slots=True)
class ToolCallRequest:
    tool: ToolSpec
    call: ToolCall


@dataclass(frozen=True, slots=True)
class ToolGuardDecision:
    action: ToolAction
    reason: str = ""
    rule_id: str | None = None
    scope: str | None = None


class HookError(RuntimeError):
    pass


HookHandler = Callable[[Any], Awaitable[Any] | Any]


@dataclass(frozen=True, slots=True)
class Hook:
    phase: HookPhase
    handler: HookHandler
    name: str
    priority: int = 100


class HookBus:
    """Priority-ordered hooks. Lower priority runs first.

    Guards are fail-closed: the first non-allow decision wins; handler errors
    are surfaced as HookError so the run can fail instead of silently allowing.
    """

    def __init__(self) -> None:
        self._hooks: list[Hook] = []

    def register(
        self,
        phase: HookPhase,
        handler: HookHandler,
        *,
        name: str | None = None,
        priority: int = 100,
    ) -> Callable[[], None]:
        hook = Hook(
            phase=phase,
            handler=handler,
            name=name or str(getattr(handler, "__name__", "hook")),
            priority=priority,
        )
        self._hooks.append(hook)
        self._hooks.sort(key=lambda item: item.priority)

        def unsubscribe() -> None:
            if hook in self._hooks:
                self._hooks.remove(hook)

        return unsubscribe

    async def transform(
        self,
        phase: HookPhase,
        value: T,
        expected_type: type[T],
    ) -> T:
        current: Any = value
        for hook in self._for_phase(phase):
            try:
                result = hook.handler(current)
                if inspect.isawaitable(result):
                    result = await result
            except Exception as exc:  # noqa: BLE001 - convert to typed hook failure
                raise HookError(f"{hook.name} failed: {exc}") from exc
            if not isinstance(result, expected_type):
                raise HookError(
                    f"{hook.name} returned {type(result).__name__}, "
                    f"expected {expected_type.__name__}"
                )
            current = result
        return current  # type: ignore[no-any-return]

    async def guard(
        self,
        phase: HookPhase,
        request: ToolCallRequest,
        *,
        default: ToolAction = ToolAction.ALLOW,
    ) -> ToolGuardDecision:
        for hook in self._for_phase(phase):
            try:
                result = hook.handler(request)
                if inspect.isawaitable(result):
                    result = await result
            except Exception as exc:  # noqa: BLE001 - guard errors fail closed
                raise HookError(f"{hook.name} failed: {exc}") from exc
            if not isinstance(result, ToolGuardDecision):
                raise HookError(f"{hook.name} must return ToolGuardDecision")
            if result.action is not ToolAction.ALLOW:
                return result
        return ToolGuardDecision(action=default, reason="default")

    def _for_phase(self, phase: HookPhase) -> tuple[Hook, ...]:
        return tuple(hook for hook in self._hooks if hook.phase is phase)
