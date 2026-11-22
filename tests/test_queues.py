from __future__ import annotations

from pyouroboros.core.messages import user_message
from pyouroboros.core.queues import MessageQueue
from pyouroboros.core.types import QueueMode


def test_queue_all_drains_and_clears() -> None:
    queue = MessageQueue(QueueMode.ALL)
    queue.enqueue(user_message("a"))
    queue.enqueue(user_message("b"))

    assert [message.text for message in queue.drain()] == ["a", "b"]
    assert not queue.has_items()


def test_queue_one_at_a_time() -> None:
    queue = MessageQueue(QueueMode.ONE_AT_A_TIME)
    queue.enqueue(user_message("a"))
    queue.enqueue(user_message("b"))

    assert [message.text for message in queue.drain()] == ["a"]
    assert [message.text for message in queue.drain()] == ["b"]
    assert not queue.has_items()
