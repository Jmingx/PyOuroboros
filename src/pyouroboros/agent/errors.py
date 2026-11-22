"""Agent-layer runtime errors."""

from __future__ import annotations


class RunBusyError(RuntimeError):
    pass


class NoActiveRunError(RuntimeError):
    pass
