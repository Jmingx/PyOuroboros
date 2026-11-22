"""Core enums and run-scoped value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pyouroboros.core.conversation import MessageSource

from pyouroboros.core.ids import ApprovalId, RunId
from pyouroboros.core.messages import Message, ToolCall


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStopReason(StrEnum):
    FINAL_ANSWER = "final_answer"
    MAX_TURNS = "max_turns"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    PROTOCOL_ERROR = "protocol_error"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NO_PROGRESS = "no_progress"
    CANCELLED = "cancelled"
    ERROR = "error"


class ModelStopReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"
    UNKNOWN = "unknown"


class ToolExecutionMode(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class QueueMode(StrEnum):
    ALL = "all"
    ONE_AT_A_TIME = "one-at-a-time"


@dataclass(frozen=True, slots=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class ModelConfig:
    provider: str
    model: str
    temperature: float | None = None


@dataclass(frozen=True, slots=True)
class ToolSchema:
    """Provider-facing tool schema, owned by the tool definition."""

    name: str
    description: str
    parameters: dict[str, object]

    def to_openai(self) -> dict[str, object]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True, slots=True)
class ToolSpec:
    schema: ToolSchema
    side_effect: Literal["read", "write", "external", "destructive"] = "read"
    execution_mode: ToolExecutionMode | None = None
    requires_approval: bool = False
    output_limit: int = 20_000
    idempotent: bool = False

    @property
    def name(self) -> str:
        return self.schema.name

    @property
    def description(self) -> str:
        return self.schema.description

    @property
    def parameters(self) -> dict[str, object]:
        return self.schema.parameters


@dataclass(frozen=True, slots=True)
class ModelCall:
    messages: tuple[Message, ...]
    tools: tuple[ToolSpec, ...] = ()
    model: ModelConfig | None = None
    stream: bool = True


@dataclass(frozen=True, slots=True)
class ModelResponse:
    message: Message
    usage: Usage = field(default_factory=Usage)
    stop_reason: ModelStopReason = ModelStopReason.UNKNOWN
    raw_stop_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AgentLoopConfig:
    model: ModelConfig
    system_prompt: str = "You are a helpful agent."
    max_turns: int = 50
    tool_execution: ToolExecutionMode = ToolExecutionMode.PARALLEL
    max_parallel_tools: int = 4
    max_tool_calls: int | None = 100
    max_seconds: float | None = None
    no_progress_repeat_limit: int = 3
    steering_mode: QueueMode = QueueMode.ONE_AT_A_TIME
    follow_up_mode: QueueMode = QueueMode.ONE_AT_A_TIME
    message_source: "MessageSource | None" = None


@dataclass(frozen=True, slots=True)
class RunRequest:
    input: Message


@dataclass(frozen=True, slots=True)
class RunResult:
    run_id: RunId
    status: RunStatus
    output: Message | None = None
    usage: Usage = field(default_factory=Usage)
    error: str | None = None
    stop_reason: RunStopReason | None = None


class ApprovalAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    id: ApprovalId
    run_id: RunId
    tool_call: ToolCall
    reason: str
    options: tuple[str, ...] = ("allow", "deny")


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    request_id: ApprovalId
    action: ApprovalAction
    reason: str = ""
