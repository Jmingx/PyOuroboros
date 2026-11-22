"""Tool subsystem."""

from pyouroboros.tools.base import Tool, ToolContext, ToolHandler
from pyouroboros.tools.builtin import register_builtins
from pyouroboros.tools.manager import ToolManager


def build_default_tool_manager() -> ToolManager:
    manager = ToolManager()
    register_builtins(manager)
    return manager


__all__ = ["Tool", "ToolContext", "ToolHandler", "ToolManager", "build_default_tool_manager"]
