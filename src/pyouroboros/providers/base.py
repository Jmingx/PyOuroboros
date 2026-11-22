"""Provider protocol used by the agent loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol

from pyouroboros.core.types import ModelCall, ModelResponse

DeltaHandler = Callable[[str], Awaitable[None]]


class ModelProvider(Protocol):
    name: str
    model: str

    async def stream(
        self,
        call: ModelCall,
        on_delta: DeltaHandler,
        cancel_event: asyncio.Event,
    ) -> ModelResponse: ...
