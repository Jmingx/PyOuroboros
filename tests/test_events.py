from __future__ import annotations

from pyouroboros.core.events import RunFinished
from pyouroboros.core.ids import RunId
from pyouroboros.core.messages import assistant_message
from pyouroboros.core.types import RunResult, RunStatus, RunStopReason, Usage
from pyouroboros.server.protocol import encode_event


def test_run_finished_payload() -> None:
    result = RunResult(
        run_id=RunId("r1"),
        status=RunStatus.COMPLETED,
        output=assistant_message("hello"),
        usage=Usage(prompt_tokens=3, completion_tokens=2),
        stop_reason=RunStopReason.FINAL_ANSWER,
    )
    kind, payload = encode_event(RunFinished(result=result))
    assert kind == "run.finished"
    assert payload["status"] == "completed"
    assert payload["output"] == "hello"
    assert payload["usage"] == {"prompt_tokens": 3, "completion_tokens": 2}
