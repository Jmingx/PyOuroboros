"""get_time tool."""

from __future__ import annotations

from datetime import datetime, timezone

from pyouroboros.core.messages import ToolCall, ToolResult
from pyouroboros.core.types import ToolSchema, ToolSpec
from pyouroboros.tools.base import Tool, ToolContext
from pyouroboros.tools.manager import ToolManager

SCHEMA = ToolSchema(
    name="get_time",
    description="Return the current UTC time.",
    parameters={"type": "object", "properties": {}, "additionalProperties": False},
)
SPEC = ToolSpec(schema=SCHEMA, side_effect="read")


async def handle(call: ToolCall, context: ToolContext) -> ToolResult:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return ToolResult(call_id=call.id, ok=True, content=now)


def register(manager: ToolManager) -> None:
    manager.register(Tool(spec=SPEC, handler=handle))
