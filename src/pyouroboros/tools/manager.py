"""Instance-scoped tool manager.

Unlike a module-global registry, a manager can be scoped to a session,
plugin set, subagent, or test without cross-contamination.
"""

from __future__ import annotations

from pyouroboros.core.types import ToolSchema, ToolSpec
from pyouroboros.tools.base import Tool


class ToolManager:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        name = tool.spec.name
        if name in self._tools:
            raise ValueError(f"duplicate tool: {name}")
        self._tools[name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self) -> tuple[ToolSpec, ...]:
        return tuple(tool.spec for tool in self._tools.values())

    def schemas(self) -> tuple[ToolSchema, ...]:
        return tuple(tool.spec.schema for tool in self._tools.values())

    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)
