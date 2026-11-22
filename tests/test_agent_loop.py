from __future__ import annotations

import asyncio

import pytest

from pyouroboros.agent import Agent, AgentContext, AgentSettings
from pyouroboros.core.approval import ApprovalService
from pyouroboros.core.events import ApprovalRequested, EventBus, ModelDelta, RunFinished
from pyouroboros.core.hooks import HookBus
from pyouroboros.core.messages import user_message
from pyouroboros.core.outcomes import OutcomeResolver
from pyouroboros.core.session import Session
from pyouroboros.core.types import ApprovalAction, ModelConfig, RunStatus
from pyouroboros.plugins import PluginManager, default_plugin_roots
from pyouroboros.providers.fake import FakeProvider
from pyouroboros.tools import build_default_tool_manager


def make_agent(session: Session, bus: EventBus) -> Agent:
    tools = build_default_tool_manager()
    hooks = HookBus()
    plugins = PluginManager(default_plugin_roots())
    plugins.discover()
    plugins.load()
    plugin_session = plugins.activate(hooks, tools, {"mode": "auto"})
    context = AgentContext(
        session=session,
        provider=FakeProvider(),
        tools=tools,
        events=bus,
        hooks=hooks,
        approvals=ApprovalService(),
        outcomes=OutcomeResolver(),
        settings=AgentSettings(
            model=ModelConfig(provider="fake", model="fake-echo"),
            max_turns=4,
        ),
        plugins=plugin_session,
    )
    return context.agent


async def test_fake_provider_streams_and_completes(tmp_path) -> None:
    bus = EventBus()
    events: list[object] = []
    deltas: list[str] = []

    async def on_event(event: object) -> None:
        events.append(event)
        if isinstance(event, ModelDelta):
            deltas.append(event.text)

    bus.on_any(on_event)
    session = Session(workspace=tmp_path)
    agent = make_agent(session, bus)
    agent.start(user_message("hello"))
    result = await agent.wait()

    assert result.status is RunStatus.COMPLETED
    assert result.output is not None
    assert "Fake echo: hello" in result.output.text
    assert "".join(deltas) == result.output.text
    assert any(isinstance(event, RunFinished) for event in events)
    assert len(session.messages) == 2


async def test_approval_allow_executes_tool(tmp_path) -> None:
    bus = EventBus()
    session = Session(workspace=tmp_path)
    agent = make_agent(session, bus)
    decision_ready = asyncio.Event()

    async def on_event(event: object) -> None:
        if isinstance(event, ApprovalRequested):
            assert event.request.tool_call.name == "write_note"
            agent.approvals.resolve(event.request.id, ApprovalAction.ALLOW, "test")
            decision_ready.set()

    bus.on_any(on_event)
    agent.start(user_message("please write a note about tests"))
    result = await agent.wait()

    assert decision_ready.is_set()
    assert result.status is RunStatus.COMPLETED
    assert (tmp_path / "notes").is_dir()
    assert list((tmp_path / "notes").glob("*.md"))


async def test_approval_deny_does_not_execute_tool(tmp_path) -> None:
    bus = EventBus()
    session = Session(workspace=tmp_path)
    agent = make_agent(session, bus)

    async def on_event(event: object) -> None:
        if isinstance(event, ApprovalRequested):
            agent.approvals.resolve(event.request.id, ApprovalAction.DENY, "no")

    bus.on_any(on_event)
    agent.start(user_message("write a note but I will deny it"))
    result = await agent.wait()

    assert result.status is RunStatus.COMPLETED
    assert not (tmp_path / "notes").exists()


@pytest.mark.asyncio
async def test_cancel_stops_run(tmp_path) -> None:
    session = Session(workspace=tmp_path)
    agent = make_agent(session, EventBus())
    agent.start(user_message("hello"))
    await asyncio.sleep(0.01)
    agent.cancel()
    result = await agent.wait()
    assert result.status is RunStatus.CANCELLED
