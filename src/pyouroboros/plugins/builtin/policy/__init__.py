"""Built-in policy plugin."""

from __future__ import annotations

from pyouroboros.core.hooks import HookPhase
from pyouroboros.core.policy import PolicyEngine, PolicyMode
from pyouroboros.plugins.manager import PluginContext

from .guard import PolicyGuard

__all__ = ["PolicyGuard", "register"]


def register(ctx: PluginContext) -> None:
    raw_mode = str(ctx.config.get("mode", "auto"))
    try:
        mode = PolicyMode(raw_mode)
    except ValueError:
        mode = PolicyMode.AUTO
    ctx.hooks.register(
        HookPhase.BEFORE_TOOL_CALL,
        PolicyGuard(PolicyEngine(mode=mode)),
        name="policy",
        priority=10,
    )
