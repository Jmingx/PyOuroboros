"""Built-in tools, one module per capability."""

from __future__ import annotations

from pyouroboros.tools.manager import ToolManager


def register_builtins(manager: ToolManager) -> None:
    from pyouroboros.tools.builtin import echo, get_time, write_note

    for module in (get_time, echo, write_note):
        module.register(manager)
