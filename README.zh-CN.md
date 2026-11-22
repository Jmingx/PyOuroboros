# PyOuroboros

一个类型安全、可插件扩展的 agent harness。第一版是本地 Web 聊天：流式输出 + 工具审批。

[English](README.md) | 简体中文

## 已实现

- Python 3.12 + FastAPI + WebSocket 后端。
- TypeScript + React 18 + Vite 前端。
- DeepSeek `deepseek-flash`（OpenAI 兼容流式接口）。
- 确定性 `fake` provider，本地演示与测试不需要密钥。
- 工具调用（`get_time`、`echo`、`write_note`）+ 对话内审批卡。
- WebSocket 协议：run start / cancel / steer / approval。
- 会话暂存内存；SQLite/JSONL 持久化是下一刀。

架构文档在 [docs/architecture](docs/architecture/overview.md)。

## 快速开始

前置：Python 3.12、[uv](https://docs.astral.sh/uv/)、Node.js 20+。

```powershell
uv sync
Copy-Item .env.example .env
# 编辑 .env 填 DEEPSEEK_API_KEY；或强制 fake：
# $env:PYOUROBOROS_PROVIDER = "fake"

cd web
npm install
npm run build
cd ..

uv run uvicorn pyouroboros.server.app:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000>。

如果 `DEEPSEEK_API_KEY` 为空，服务端自动回退到 `fake` provider。

### 前端开发模式

后端跑 8000，然后：

```powershell
cd web
npm run dev
```

打开 <http://127.0.0.1:5173>；Vite 会代理 `/ws` 和 `/api` 到后端。

## 检查

```powershell
uv run ruff check src tests
uv run mypy src
uv run pytest -q
cd web; npm run build
```

## 状态

这是垂直切片，不是完整 v1。Session tree/fork、SQLite 持久化、插件加载、MCP 还在路线图上，见 [v1-checklist](docs/architecture/v1-checklist.md)。
