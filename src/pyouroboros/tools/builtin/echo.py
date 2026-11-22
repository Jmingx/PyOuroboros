"""echo tool."""

from __future__ import annotations

from pyouroboros.core.messages import ToolCall, ToolResult
from pyouroboros.core.types import ToolSchema, ToolSpec
from pyouroboros.tools.base import Tool, ToolContext
from pyouroboros.tools.manager import ToolManager

SCHEMA = ToolSchema(
    name="echo",
    description="Echo text back. Useful for connectivity tests.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
)
SPEC = ToolSpec(schema=SCHEMA, side_effect="read")


async def handle(call: ToolCall, context: ToolContext) -> ToolResult:
    return ToolResult(call_id=call.id, ok=True, content=str(call.arguments.get("text", "")))


def register(manager: ToolManager) -> None:
    manager.register(Tool(spec=SPEC, handler=handle))
