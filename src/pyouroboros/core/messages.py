"""Conversation value objects.

Vendor payloads are parsed into these types at the provider boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pyouroboros.core.ids import MessageId, ToolCallId

Role = Literal["system", "user", "assistant", "tool"]
MessageSource = Literal["system", "user", "assistant", "tool", "plugin", "subagent"]


@dataclass(frozen=True, slots=True)
class TextBlock:
    text: str


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: ToolCallId
    name: str
    arguments: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    call_id: ToolCallId
    ok: bool
    content: str
    error: str | None = None
    terminate: bool = False


type ContentBlock = TextBlock | ToolCall | ToolResult


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: tuple[ContentBlock, ...]
    source: MessageSource = "user"
    id: MessageId | None = None

    @property
    def text(self) -> str:
        return "\n".join(block.text for block in self.content if isinstance(block, TextBlock))

    @property
    def tool_calls(self) -> tuple[ToolCall, ...]:
        return tuple(block for block in self.content if isinstance(block, ToolCall))

    @property
    def tool_result(self) -> ToolResult | None:
        for block in self.content:
            if isinstance(block, ToolResult):
                return block
        return None


def user_message(text: str) -> Message:
    return Message(role="user", content=(TextBlock(text),), source="user")


def system_message(text: str) -> Message:
    return Message(role="system", content=(TextBlock(text),), source="system")


def assistant_message(
    text: str = "", tool_calls: tuple[ToolCall, ...] = ()
) -> Message:
    blocks: list[ContentBlock] = []
    if text:
        blocks.append(TextBlock(text))
    blocks.extend(tool_calls)
    return Message(role="assistant", content=tuple(blocks), source="assistant")


def tool_message(result: ToolResult) -> Message:
    return Message(role="tool", content=(result,), source="tool")
