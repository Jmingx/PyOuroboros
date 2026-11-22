"""Session-scoped agent settings, independent of transport and Run."""

from __future__ import annotations

import os
from dataclasses import dataclass

from pyouroboros.core.types import (
    AgentLoopConfig,
    ModelConfig,
    QueueMode,
    ToolExecutionMode,
)


@dataclass(frozen=True, slots=True)
class AgentSettings:
    model: ModelConfig
    system_prompt: str = "You are a helpful agent."
    max_turns: int = 50
    max_tool_calls: int | None = 100
    max_seconds: float | None = None
    no_progress_repeat_limit: int = 3
    tool_execution: ToolExecutionMode = ToolExecutionMode.PARALLEL
    max_parallel_tools: int = 4
    steering_mode: QueueMode = QueueMode.ONE_AT_A_TIME
    follow_up_mode: QueueMode = QueueMode.ONE_AT_A_TIME

    def to_loop_config(self) -> AgentLoopConfig:
        return AgentLoopConfig(
            model=self.model,
            system_prompt=self.system_prompt,
            max_turns=self.max_turns,
            max_tool_calls=self.max_tool_calls,
            max_seconds=self.max_seconds,
            no_progress_repeat_limit=self.no_progress_repeat_limit,
            tool_execution=self.tool_execution,
            max_parallel_tools=self.max_parallel_tools,
            steering_mode=self.steering_mode,
            follow_up_mode=self.follow_up_mode,
        )

    @classmethod
    def from_env(cls, provider: str, model: str) -> "AgentSettings":
        return cls(
            model=ModelConfig(
                provider=provider,
                model=model,
                temperature=float(os.getenv("DEEPSEEK_TEMPERATURE", "0.2")),
            ),
            max_turns=int(os.getenv("PYOUROBOROS_MAX_TURNS", "50")),
            max_tool_calls=int(os.getenv("PYOUROBOROS_MAX_TOOL_CALLS", "100")),
        )
