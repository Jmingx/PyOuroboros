from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from pyouroboros.core.messages import system_message, user_message
from pyouroboros.core.types import ModelCall, ModelStopReason
from pyouroboros.providers.deepseek import DeepSeekProvider


def sse(*chunks: dict[str, object]) -> bytes:
    lines = [f"data: {json.dumps(chunk, ensure_ascii=False)}" for chunk in chunks]
    lines.append("data: [DONE]")
    return ("\n\n".join(lines) + "\n\n").encode()


def make_provider(content: bytes) -> DeepSeekProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "deepseek-flash"
        assert payload["stream"] is True
        return httpx.Response(200, content=content, headers={"content-type": "text/event-stream"})

    return DeepSeekProvider(
        api_key="test",
        base_url="https://example.test",
        model="deepseek-flash",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_deepseek_streams_text_and_usage() -> None:
    content = sse(
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
        {
            "choices": [{"delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        },
    )
    provider = make_provider(content)
    deltas: list[str] = []

    async def on_delta(text: str) -> None:
        deltas.append(text)

    response = await provider.stream(
        ModelCall(messages=(system_message("s"), user_message("hi"))),
        on_delta,
        asyncio.Event(),
    )

    assert deltas == ["Hel", "lo"]
    assert response.message.text == "Hello"
    assert response.usage.prompt_tokens == 5
    assert response.usage.completion_tokens == 2
    assert response.stop_reason is ModelStopReason.STOP


@pytest.mark.asyncio
async def test_deepseek_assembles_tool_call_deltas() -> None:
    content = sse(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "write_note", "arguments": "{\"text\":"},
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": "\"hello\"}"},
                            }
                        ]
                    }
                }
            ]
        },
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
    )
    provider = make_provider(content)

    async def on_delta(text: str) -> None:
        return None

    response = await provider.stream(
        ModelCall(messages=(system_message("s"), user_message("write a note"))),
        on_delta,
        asyncio.Event(),
    )

    assert response.stop_reason is ModelStopReason.TOOL_CALLS
    assert len(response.message.tool_calls) == 1
    call = response.message.tool_calls[0]
    assert call.id == "call_1"
    assert call.name == "write_note"
    assert call.arguments == {"text": "hello"}
