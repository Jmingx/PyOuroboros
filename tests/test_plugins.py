from __future__ import annotations

from pyouroboros.core.hooks import HookBus, HookPhase, ToolAction, ToolCallRequest
from pyouroboros.core.ids import ToolCallId
from pyouroboros.core.messages import ToolCall
from pyouroboros.core.types import ToolSchema, ToolSpec
from pyouroboros.plugins import PluginManager, default_plugin_roots
from pyouroboros.tools import build_default_tool_manager


def test_builtin_policy_plugin_registers_guard() -> None:
    manager = PluginManager(default_plugin_roots())
    manifests = manager.discover()
    assert any(item.name == "policy" for item in manifests)
    manager.load()

    hooks = HookBus()
    tools = build_default_tool_manager()
    session = manager.activate(hooks, tools, {"mode": "auto"})
    assert session.contexts[0].name == "policy"

    tool = ToolSpec(
        schema=ToolSchema(
            name="write_note",
            description="write",
            parameters={"type": "object", "properties": {}},
        ),
        side_effect="write",
    )
    request = ToolCallRequest(
        tool=tool,
        call=ToolCall(id=ToolCallId("c1"), name="write_note", arguments={}),
    )

    import asyncio

    decision = asyncio.run(hooks.guard(HookPhase.BEFORE_TOOL_CALL, request))
    assert decision.action is ToolAction.ASK
