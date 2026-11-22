"""Small in-house message queues; no third-party queue dependency."""

from __future__ import annotations

from collections import deque

from pyouroboros.core.messages import Message
from pyouroboros.core.types import QueueMode


class MessageQueue:
    """FIFO queue with explicit drain semantics.

    - `all`: snapshot every message and clear the queue.
    - `one-at-a-time`: pop only the oldest message.
    """

    def __init__(self, mode: QueueMode = QueueMode.ONE_AT_A_TIME) -> None:
        self.mode = mode
        self._items: deque[Message] = deque()

    def enqueue(self, message: Message) -> None:
        self._items.append(message)

    def drain(self, mode: QueueMode | None = None) -> tuple[Message, ...]:
        selected = mode or self.mode
        if selected is QueueMode.ALL:
            items = tuple(self._items)
            self._items.clear()
            return items
        if not self._items:
            return ()
        return (self._items.popleft(),)

    def peek(self, mode: QueueMode | None = None) -> tuple[Message, ...]:
        selected = mode or self.mode
        if selected is QueueMode.ALL:
            return tuple(self._items)
        if not self._items:
            return ()
        return (self._items[0],)

    def has_items(self) -> bool:
        return bool(self._items)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
