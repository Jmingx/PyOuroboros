"""In-memory session state for the first vertical slice."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pyouroboros.core.ids import SessionId
from pyouroboros.core.messages import Message


@dataclass
class Session:
    id: SessionId = field(default_factory=lambda: SessionId(uuid.uuid4().hex))
    messages: list[Message] = field(default_factory=list)
    workspace: Path = field(default_factory=lambda: Path.cwd() / "runtime" / "workspace")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def append(self, message: Message) -> None:
        self.messages.append(message)

    def history(self) -> tuple[Message, ...]:
        return tuple(self.messages)
