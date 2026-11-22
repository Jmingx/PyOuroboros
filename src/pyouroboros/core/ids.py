"""Typed identifiers shared by the core."""

from typing import NewType

SessionId = NewType("SessionId", str)
RunId = NewType("RunId", str)
ToolCallId = NewType("ToolCallId", str)
MessageId = NewType("MessageId", str)
ApprovalId = NewType("ApprovalId", str)
