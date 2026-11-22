"""FastAPI WebSocket server exposing a JSON-RPC 2.0 API."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from pyouroboros.agent import (
    AgentContext,
    AgentSettings,
    NoActiveRunError,
    RunBusyError,
)
from pyouroboros.core.approval import ApprovalService
from pyouroboros.core.events import EventBus
from pyouroboros.core.hooks import HookBus
from pyouroboros.core.messages import user_message
from pyouroboros.core.outcomes import OutcomeResolver
from pyouroboros.core.session import Session
from pyouroboros.plugins import PluginManager, default_plugin_roots
from pyouroboros.providers.base import ModelProvider
from pyouroboros.providers.deepseek import DeepSeekProvider
from pyouroboros.providers.fake import FakeProvider
from pyouroboros.server.protocol import encode_event
from pyouroboros.tools import ToolManager, build_default_tool_manager

ROOT = Path(__file__).resolve().parents[3]
WEB_DIST = ROOT / "web" / "dist"


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"]
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def error_response(
    request_id: str | int | None,
    code: int,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def result_response(request_id: str | int, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def build_provider() -> tuple[ModelProvider, str]:
    load_dotenv(ROOT / ".env")
    requested = os.getenv("PYOUROBOROS_PROVIDER", "").strip().lower()
    provider: ModelProvider
    has_key = bool(os.getenv("DEEPSEEK_API_KEY", "").strip())
    if requested == "fake" or (not requested and not has_key):
        provider = FakeProvider()
        return provider, provider.model
    try:
        provider = DeepSeekProvider()
    except ValueError:
        fallback = FakeProvider()
        return fallback, fallback.model
    return provider, provider.model


class Connection:
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        session = Session()
        self.bus = EventBus()
        self.tools: ToolManager = build_default_tool_manager()
        self.provider, self.model_name = build_provider()

        hooks = HookBus()
        plugins = PluginManager(default_plugin_roots())
        plugins.discover()
        plugins.load()
        plugin_session = plugins.activate(
            hooks,
            self.tools,
            {"mode": os.getenv("PYOUROBOROS_POLICY_MODE", "auto")},
        )
        self.context = AgentContext(
            session=session,
            provider=self.provider,
            tools=self.tools,
            events=self.bus,
            hooks=hooks,
            approvals=ApprovalService(),
            outcomes=OutcomeResolver(),
            settings=AgentSettings.from_env(self.provider.name, self.model_name),
            plugins=plugin_session,
        )
        self._send_lock = asyncio.Lock()
        self.bus.on_any(self._forward_event)

    async def send(self, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
        async with self._send_lock:
            with contextlib.suppress(Exception):
                await self.websocket.send_json(payload)

    async def send_notification(self, method: str, params: dict[str, Any]) -> None:
        await self.send({"jsonrpc": "2.0", "method": method, "params": params})

    async def _forward_event(self, event: Any) -> None:
        method, params = encode_event(event)
        await self.send_notification(method, params)

    async def run_loop(self) -> None:
        await self.websocket.accept()
        await self.send_notification(
            "session.ready",
            {
                "session_id": self.context.session.id,
                "provider": self.provider.name,
                "model": self.model_name,
                "tools": list(self.tools.names()),
            },
        )
        try:
            while True:
                raw_text = await self.websocket.receive_text()
                try:
                    raw = json.loads(raw_text)
                except json.JSONDecodeError:
                    await self.send(error_response(None, -32700, "parse error"))
                    continue
                await self.handle_payload(raw)
        except WebSocketDisconnect:
            pass
        finally:
            self.context.cancel()

    async def handle_payload(self, raw: Any) -> None:
        if isinstance(raw, list):
            if not raw:
                await self.send(error_response(None, -32600, "empty batch"))
                return
            responses = []
            for item in raw:
                response = await self.process_request(item)
                if response is not None:
                    responses.append(response)
            if responses:
                await self.send(responses)
            return
        response = await self.process_request(raw)
        if response is not None:
            await self.send(response)

    async def process_request(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return error_response(None, -32600, "invalid request")
        try:
            request = JsonRpcRequest.model_validate(raw)
        except ValidationError as exc:
            return error_response(None, -32600, "invalid request", exc.errors())
        if request.id is None:
            with contextlib.suppress(RpcError):
                await self.call(request.method, request.params)
            return None
        try:
            result = await self.call(request.method, request.params)
        except RpcError as exc:
            return error_response(request.id, exc.code, exc.message, exc.data)
        except Exception as exc:  # noqa: BLE001 - protocol boundary
            return error_response(request.id, -32603, "internal error", str(exc))
        return result_response(request.id, result)

    async def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "run.start":
            text = str(params.get("text", "")).strip()
            if not text:
                raise RpcError(-32602, "text is required")
            if self.context.is_running:
                raise RpcError(-32002, "a run is already active")
            try:
                run_id = self.context.start(user_message(text))
            except RunBusyError as exc:
                raise RpcError(-32002, str(exc)) from exc
            return {"run_id": run_id}
        if method == "run.cancel":
            self.context.cancel()
            return {"ok": True}
        if method in ("run.steer", "run.follow_up"):
            await self._queue_input(params, follow_up=method == "run.follow_up")
            return {"ok": True}
        if method == "approval.decide":
            request_id = str(params.get("request_id", ""))
            action = str(params.get("action", ""))
            if action not in ("allow", "deny"):
                raise RpcError(-32602, "action must be allow or deny")
            try:
                resolved = self.context.approve(request_id, action)
            except NoActiveRunError as exc:
                raise RpcError(-32001, str(exc)) from exc
            if not resolved:
                raise RpcError(-32003, f"unknown approval: {request_id}")
            return {"ok": True}
        raise RpcError(-32601, f"method not found: {method}")

    async def _queue_input(self, params: dict[str, Any], *, follow_up: bool) -> None:
        text = str(params.get("text", "")).strip()
        if not text:
            raise RpcError(-32602, "text is required")
        try:
            message = user_message(text)
            if follow_up:
                self.context.follow_up(message)
            else:
                self.context.steer(message)
        except NoActiveRunError as exc:
            raise RpcError(-32001, str(exc)) from exc


def create_app() -> FastAPI:
    app = FastAPI(title="PyOuroboros", version="0.1.0")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        provider, model = build_provider()
        return {"status": "ok", "provider": provider.name, "model": model}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        connection = Connection(websocket)
        await connection.run_loop()

    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
    else:

        @app.get("/", response_class=HTMLResponse)
        async def placeholder() -> str:
            return (
                "<h1>PyOuroboros</h1>"
                "<p>Frontend not built. Run <code>cd web &amp;&amp; npm install"
                " &amp;&amp; npm run build</code>.</p>"
            )

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "pyouroboros.server.app:app",
        host=os.getenv("PYOUROBOROS_HOST", "127.0.0.1"),
        port=int(os.getenv("PYOUROBOROS_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
