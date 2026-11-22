from __future__ import annotations

from fastapi.testclient import TestClient

from pyouroboros.server.app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["provider"] in {"fake", "deepseek"}


def test_jsonrpc_chat(monkeypatch) -> None:
    monkeypatch.setenv("PYOUROBOROS_PROVIDER", "fake")
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as ws:
        ready = ws.receive_json()
        assert ready["jsonrpc"] == "2.0"
        assert ready["method"] == "session.ready"
        assert ready["params"]["provider"] == "fake"

        ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "run.start",
                "params": {"text": "hello"},
            }
        )
        methods: list[str] = []
        response_seen = False
        while not (response_seen and "run.finished" in methods):
            message = ws.receive_json()
            if message.get("id") == 1:
                response_seen = True
                assert "result" in message
                assert message["result"]["run_id"]
            else:
                methods.append(message["method"])
        assert "model.delta" in methods
        assert "model.finished" in methods
        assert "run.finished" in methods


def test_jsonrpc_method_not_found(monkeypatch) -> None:
    monkeypatch.setenv("PYOUROBOROS_PROVIDER", "fake")
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()  # session.ready notification
        ws.send_json({"jsonrpc": "2.0", "id": 2, "method": "no.such.method", "params": {}})
        response = ws.receive_json()
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert response["error"]["code"] == -32601


def test_jsonrpc_parse_error(monkeypatch) -> None:
    monkeypatch.setenv("PYOUROBOROS_PROVIDER", "fake")
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()  # session.ready notification
        ws.send_text("{not-json")
        response = ws.receive_json()
        assert response["jsonrpc"] == "2.0"
        assert response["id"] is None
        assert response["error"]["code"] == -32700
