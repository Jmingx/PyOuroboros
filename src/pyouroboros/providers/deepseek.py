"""DeepSeek OpenAI-compatible streaming provider."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from pyouroboros.core.ids import ToolCallId
from pyouroboros.core.messages import Message, ToolCall, assistant_message
from pyouroboros.core.types import (
    ModelCall,
    ModelResponse,
    ModelStopReason,
    Usage,
)
from pyouroboros.providers.base import DeltaHandler

_STOP_REASONS = {
    "stop": ModelStopReason.STOP,
    "length": ModelStopReason.LENGTH,
    "tool_calls": ModelStopReason.TOOL_CALLS,
    "content_filter": ModelStopReason.CONTENT_FILTER,
}


class DeepSeekProvider:
    name = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
        self.model: str = model or os.getenv("DEEPSEEK_MODEL") or "deepseek-flash"
        self.timeout = timeout
        self.transport = transport
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set")

    async def stream(
        self,
        call: ModelCall,
        on_delta: DeltaHandler,
        cancel_event: asyncio.Event,
    ) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": call.model.model if call.model else self.model,
            "messages": [self._to_wire(message) for message in call.messages],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if call.model and call.model.temperature is not None:
            payload["temperature"] = call.model.temperature
        if call.tools:
            payload["tools"] = [tool.schema.to_openai() for tool in call.tools]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        text_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}
        usage = Usage()
        raw_stop: str | None = None

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                transport=self.transport,
            ) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", "replace")
                        raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {body[:500]}")
                    async for line in response.aiter_lines():
                        if cancel_event.is_set():
                            raise asyncio.CancelledError
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        if chunk.get("usage"):
                            usage = Usage(
                                prompt_tokens=int(chunk["usage"].get("prompt_tokens", 0)),
                                completion_tokens=int(chunk["usage"].get("completion_tokens", 0)),
                            )
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        raw_stop = choice.get("finish_reason") or raw_stop
                        delta = choice.get("delta") or {}
                        content = delta.get("content")
                        if content:
                            text_parts.append(content)
                            await on_delta(content)
                        for part in delta.get("tool_calls") or []:
                            index = int(part.get("index", 0))
                            slot = tool_calls.setdefault(
                                index,
                                {"id": "", "name": "", "arguments": ""},
                            )
                            if part.get("id"):
                                slot["id"] = part["id"]
                            function = part.get("function") or {}
                            if function.get("name"):
                                slot["name"] += function["name"]
                            if function.get("arguments"):
                                slot["arguments"] += function["arguments"]
        except httpx.HTTPError as exc:
            raise RuntimeError(f"DeepSeek request failed: {exc}") from exc

        calls = tuple(
            ToolCall(
                id=ToolCallId(slot["id"] or f"call_{index}"),
                name=slot["name"],
                arguments=self._parse_arguments(slot["arguments"]),
            )
            for index, slot in sorted(tool_calls.items())
            if slot["name"]
        )
        text = "".join(text_parts)
        stop_reason = _STOP_REASONS.get(raw_stop or "", ModelStopReason.UNKNOWN)
        if calls and stop_reason is ModelStopReason.UNKNOWN:
            stop_reason = ModelStopReason.TOOL_CALLS
        if not text and not calls:
            stop_reason = ModelStopReason.ERROR
        return ModelResponse(
            message=assistant_message(text, calls),
            usage=usage,
            stop_reason=stop_reason,
            raw_stop_reason=raw_stop,
        )

    @staticmethod
    def _parse_arguments(raw: str) -> dict[str, Any]:
        if not raw.strip():
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid tool arguments: {raw[:300]}") from exc
        if not isinstance(value, dict):
            raise RuntimeError("tool arguments must be a JSON object")
        return value

    @staticmethod
    def _to_wire(message: Message) -> dict[str, Any]:
        if message.role in ("system", "user"):
            return {"role": message.role, "content": message.text}
        if message.role == "tool":
            result = message.tool_result
            if result is None:
                return {"role": "tool", "content": ""}
            content = result.content if result.ok else (result.error or "tool failed")
            return {
                "role": "tool",
                "tool_call_id": result.call_id,
                "content": content,
            }
        wire: dict[str, Any] = {"role": "assistant", "content": message.text or None}
        if message.tool_calls:
            wire["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in message.tool_calls
            ]
        return wire


async def iter_sse(lines: AsyncIterator[str]) -> AsyncIterator[dict[str, Any]]:
    """Small helper used by tests and future providers."""

    async for line in lines:
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            break
        yield json.loads(data)
