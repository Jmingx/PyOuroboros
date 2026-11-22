"""write_note tool."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from pyouroboros.core.messages import ToolCall, ToolResult
from pyouroboros.core.types import ToolSchema, ToolSpec
from pyouroboros.tools.base import Tool, ToolContext
from pyouroboros.tools.manager import ToolManager

SCHEMA = ToolSchema(
    name="write_note",
    description="Save a short note into the workspace notes directory.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
)
SPEC = ToolSpec(schema=SCHEMA, side_effect="write", requires_approval=True)


async def handle(call: ToolCall, context: ToolContext) -> ToolResult:
    text = str(call.arguments.get("text", "")).strip()
    if not text:
        return ToolResult(call_id=call.id, ok=False, content="", error="text is required")
    notes = context.workspace / "notes"
    await asyncio.to_thread(notes.mkdir, parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = notes / f"note-{stamp}.md"
    await asyncio.to_thread(path.write_text, text, "utf-8")
    return ToolResult(call_id=call.id, ok=True, content=f"saved {path.name}")


def register(manager: ToolManager) -> None:
    manager.register(Tool(spec=SPEC, handler=handle))
