# PyOuroboros

A type-safe, plugin-extensible agent harness. The first slice is a local Web chat with streaming output and tool approval.

English | [简体中文](README.zh-CN.md)

## What works

- Python 3.12 + FastAPI + WebSocket backend.
- TypeScript + React 18 + Vite frontend.
- DeepSeek `deepseek-flash` through the OpenAI-compatible streaming API.
- Deterministic `fake` provider for local demos and tests.
- Tool calls (`get_time`, `echo`, `write_note`) with an inline approval card.
- WebSocket protocol for run start / cancel / steer / approval.
- In-memory session for now; SQLite/JSONL persistence is the next slice.

Architecture notes live in [docs/architecture](docs/architecture/overview.md).

## Quickstart

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 20+.

```powershell
uv sync
Copy-Item .env.example .env
# edit .env and set DEEPSEEK_API_KEY, or force the fake provider:
# $env:PYOUROBOROS_PROVIDER = "fake"

cd web
npm install
npm run build
cd ..

uv run uvicorn pyouroboros.server.app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>.

If `DEEPSEEK_API_KEY` is empty, the server falls back to the deterministic `fake` provider.

### Frontend dev mode

Run the backend on port 8000, then:

```powershell
cd web
npm run dev
```

Open <http://127.0.0.1:5173>; Vite proxies `/ws` and `/api` to the backend.

## Checks

```powershell
uv run ruff check src tests
uv run mypy src
uv run pytest -q
cd web; npm run build
```

## Status

This is a vertical slice, not the full v1. Session tree/fork, SQLite persistence, plugin loading, and MCP are still on the roadmap; see [v1-checklist](docs/architecture/v1-checklist.md).
