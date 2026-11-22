from __future__ import annotations

from pyouroboros.core.ids import RunId
from pyouroboros.core.messages import user_message
from pyouroboros.core.queues import MessageQueue
from pyouroboros.core.run import Run
from pyouroboros.core.session import Session
from pyouroboros.core.types import AgentLoopConfig, ModelConfig, QueueMode
from pyouroboros.tools import build_default_tool_manager


def test_tool_manager_owns_schemas() -> None:
    manager = build_default_tool_manager()
    names = manager.names()
    assert "get_time" in names
    assert "write_note" in names
    spec = manager.get("write_note")
    assert spec is not None
    assert spec.spec.schema.name == "write_note"
    assert spec.spec.schema.parameters["required"] == ["text"]
    assert spec.spec.requires_approval is True


def test_run_has_separate_queues(tmp_path) -> None:
    config = AgentLoopConfig(
        model=ModelConfig(provider="fake", model="fake"),
        steering_mode=QueueMode.ALL,
        follow_up_mode=QueueMode.ONE_AT_A_TIME,
    )
    run = Run(
        id=RunId("r1"),
        config=config,
        session=Session(workspace=tmp_path),
    )
    run.steer(user_message("now"))
    run.follow_up(user_message("later"))

    assert [m.text for m in run.steer_queue.drain()] == ["now"]
    assert [m.text for m in run.follow_up_queue.drain()] == ["later"]
    assert isinstance(run.steer_queue, MessageQueue)
    assert run.steer_queue is not run.follow_up_queue
