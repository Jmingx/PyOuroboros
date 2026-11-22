import { useEffect, useRef, useState } from 'react'
import type { ApprovalRequest, ServerEnvelope } from './protocol'

type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'tool'
  text: string
  tool?: {
    name: string
    args: Record<string, unknown>
    running: boolean
    ok?: boolean
    error?: string | null
  }
}

type UsageState = { prompt_tokens: number; completion_tokens: number }

const nowId = (): string =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`

const wsUrl = (): string =>
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`

const toolLabel = (name: string): string => {
  if (name === 'get_time') return '读取时间'
  if (name === 'write_note') return '写入笔记'
  if (name === 'echo') return '回声'
  return name
}

function ApprovalCard({
  approval,
  onDecide,
}: {
  approval: ApprovalRequest
  onDecide: (requestId: string, action: string) => void
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const answered = useRef(false)
  const [seconds, setSeconds] = useState(60)

  const answer = (action: string) => {
    if (answered.current) return
    answered.current = true
    setBusy(action)
    onDecide(approval.request_id, action)
  }

  useEffect(() => {
    const timer = window.setInterval(() => {
      setSeconds((value) => {
        if (value <= 1) {
          window.clearInterval(timer)
          answer('deny')
          return 0
        }
        return value - 1
      })
    }, 1000)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="approval-card">
      <div className="approval-top">
        <span className="badge warning">需要审批</span>
        <span className="muted">剩余 {seconds}s</span>
      </div>
      <div className="approval-title">
        {toolLabel(approval.tool_name)}
        <code>{approval.tool_name}</code>
      </div>
      <p className="approval-reason">{approval.reason}</p>
      <pre className="approval-args">{JSON.stringify(approval.arguments, null, 2)}</pre>
      <div className="approval-actions">
        <button className="btn danger" disabled={busy !== null} onClick={() => answer('deny')}>
          拒绝
        </button>
        <button className="btn primary" disabled={busy !== null} onClick={() => answer('allow')}>
          {busy === 'allow' ? '提交中…' : '允许一次'}
        </button>
      </div>
    </div>
  )
}

function ToolCard({ message }: { message: ChatMessage }) {
  const tool = message.tool!
  return (
    <div className={`tool-card ${tool.running ? 'running' : tool.ok ? 'ok' : 'bad'}`}>
      <div className="tool-head">
        <span className="tool-dot" />
        <strong>{toolLabel(tool.name)}</strong>
        <code>{tool.name}</code>
        <span className="muted">{tool.running ? '执行中…' : tool.ok ? '完成' : '失败'}</span>
      </div>
      <pre className="tool-args">{JSON.stringify(tool.args, null, 2)}</pre>
      {!tool.running && <div className="tool-result">{tool.error || message.text || '(no output)'}</div>}
    </div>
  )
}

export default function App() {
  const [connected, setConnected] = useState(false)
  const [provider, setProvider] = useState('connecting')
  const [model, setModel] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState('')
  const [running, setRunning] = useState(false)
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([])
  const [usage, setUsage] = useState<UsageState>({ prompt_tokens: 0, completion_tokens: 0 })
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const rpcIdRef = useRef(0)
  const runningRef = useRef(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    runningRef.current = running
  }, [running])

  useEffect(() => {
    let disposed = false
    let retry: number | undefined
    let socket: WebSocket | null = null

    const handleEvent = (method: string, payload: Record<string, any>) => {
      switch (method) {
        case 'session.ready':
          setConnected(true)
          setProvider(String(payload.provider ?? 'unknown'))
          setModel(String(payload.model ?? ''))
          setStatus('idle')
          break
        case 'run.started':
          setRunning(true)
          setStatus('running')
          setStreaming('')
          setError(null)
          break
        case 'model.delta':
          setStreaming((text) => text + String(payload.text ?? ''))
          break
        case 'model.finished': {
          const content = String(payload.content ?? '')
          const usage = (payload.usage ?? {}) as { prompt_tokens?: number; completion_tokens?: number }
          setUsage((prev) => ({
            prompt_tokens: prev.prompt_tokens + (usage.prompt_tokens ?? 0),
            completion_tokens: prev.completion_tokens + (usage.completion_tokens ?? 0),
          }))
          if (content.trim()) {
            setMessages((prev) => [
              ...prev,
              { id: nowId(), role: 'assistant', text: content },
            ])
          }
          setStreaming('')
          break
        }
        case 'tool.started': {
          const call = (payload.call ?? {}) as {
            id?: string
            name?: string
            arguments?: Record<string, unknown>
          }
          setMessages((prev) => [
            ...prev,
            {
              id: call.id ?? nowId(),
              role: 'tool',
              text: '',
              tool: {
                name: call.name ?? 'tool',
                args: call.arguments ?? {},
                running: true,
              },
            },
          ])
          break
        }
        case 'tool.finished': {
          const callId = String(payload.call_id ?? '')
          setMessages((prev) => {
            const exists = prev.some((item) => item.id === callId && item.tool)
            if (!exists) {
              return [
                ...prev,
                {
                  id: callId || nowId(),
                  role: 'tool',
                  text: String(payload.content ?? ''),
                  tool: {
                    name: String(payload.name ?? 'tool'),
                    args: {},
                    running: false,
                    ok: Boolean(payload.ok),
                    error: payload.error ? String(payload.error) : null,
                  },
                },
              ]
            }
            return prev.map((item) =>
              item.id === callId && item.tool
                ? {
                    ...item,
                    text: String(payload.content ?? ''),
                    tool: {
                      ...item.tool,
                      running: false,
                      ok: Boolean(payload.ok),
                      error: payload.error ? String(payload.error) : null,
                    },
                  }
                : item,
            )
          })
          break
        }
        case 'approval.requested': {
          const request = payload as unknown as ApprovalRequest
          setApprovals((prev) =>
            prev.some((item) => item.request_id === request.request_id)
              ? prev
              : [...prev, request],
          )
          break
        }
        case 'approval.resolved':
          setApprovals((prev) =>
            prev.filter((item) => item.request_id !== payload.request_id),
          )
          break
        case 'run.finished': {
          setRunning(false)
          setStreaming('')
          setStatus(String(payload.status ?? 'completed'))
          if (payload.error) setError(String(payload.error))
          break
        }
        case 'run.failed':
          setRunning(false)
          setStreaming('')
          setError(String(payload.message ?? 'run failed'))
          break
        case 'error':
          setError(String(payload.message ?? 'server error'))
          break
      }
    }

    const handleMessage = (message: ServerEnvelope | ServerEnvelope[]) => {
      if (Array.isArray(message)) {
        message.forEach(handleMessage)
        return
      }
      if ('id' in message && ('result' in message || 'error' in message)) {
        if ('error' in message && message.error) {
          setError(message.error.message)
        }
        return
      }
      if ('method' in message) {
        handleEvent(message.method, (message.params ?? {}) as Record<string, any>)
      }
    }

    const connect = () => {
      if (disposed) return
      socket = new WebSocket(wsUrl())
      wsRef.current = socket
      socket.onopen = () => setConnected(true)
      socket.onmessage = (event) => {
        try {
          handleMessage(JSON.parse(event.data) as ServerEnvelope)
        } catch {
          setError('收到无法解析的服务端消息')
        }
      }
      socket.onclose = () => {
        setConnected(false)
        if (!disposed) retry = window.setTimeout(connect, 1200)
      }
      socket.onerror = () => setConnected(false)
    }

    connect()
    return () => {
      disposed = true
      if (retry) window.clearTimeout(retry)
      socket?.close()
      wsRef.current = null
    }
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, streaming, approvals])

  const call = (method: string, params: Record<string, unknown>) => {
    const socket = wsRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setError('WebSocket 未连接')
      return
    }
    socket.send(
      JSON.stringify({
        jsonrpc: '2.0',
        id: ++rpcIdRef.current,
        method,
        params,
      }),
    )
  }

  const submit = () => {
    const text = input.trim()
    if (!text) return
    setError(null)
    if (runningRef.current) {
      call('run.steer', { text })
      setMessages((prev) => [...prev, { id: nowId(), role: 'user', text }])
    } else {
      setRunning(true)
      setStatus('running')
      call('run.start', { text })
      setMessages((prev) => [...prev, { id: nowId(), role: 'user', text }])
    }
    setInput('')
  }

  const stop = () => call('run.cancel', {})

  const decide = (requestId: string, action: string) => {
    call('approval.decide', { request_id: requestId, action })
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">◉</span>
          <div>
            <div className="brand-name">PyOuroboros</div>
            <div className="brand-sub">agent harness · web slice</div>
          </div>
        </div>
        <div className="topbar-right">
          <span className={`conn ${connected ? 'on' : 'off'}`}>
            <span className="conn-dot" />
            {connected ? 'connected' : 'offline'}
          </span>
          <span className="chip">{provider}</span>
          <span className="chip muted">{model}</span>
          <span className="usage">
            ↑{usage.prompt_tokens} ↓{usage.completion_tokens}
          </span>
        </div>
      </header>

      <main className="workspace">
        <section className="chat-panel">
          <div className="chat-scroll" ref={scrollRef}>
            {messages.length === 0 && !streaming && (
              <div className="empty">
                <div className="empty-mark">◉</div>
                <h1>开始一次 Run</h1>
                <p>纯 Python 后端，流式输出，工具审批内嵌在对话里。</p>
                <div className="suggestions">
                  <button onClick={() => setInput('现在几点了？')}>现在几点了？</button>
                  <button onClick={() => setInput('写一条 note：今天开始搭建 Web。')}>
                    写一条 note
                  </button>
                  <button onClick={() => setInput('你好，介绍一下你自己。')}>打个招呼</button>
                </div>
              </div>
            )}

            {messages.map((message) => {
              if (message.role === 'tool') return <ToolCard key={message.id} message={message} />
              return (
                <article key={message.id} className={`bubble ${message.role}`}>
                  <div className="bubble-role">{message.role === 'user' ? '你' : 'agent'}</div>
                  <div className="bubble-text">{message.text}</div>
                </article>
              )
            })}

            {streaming && (
              <article className="bubble assistant streaming">
                <div className="bubble-role">agent</div>
                <div className="bubble-text">{streaming}<span className="cursor" /></div>
              </article>
            )}

            {approvals.map((approval) => (
              <ApprovalCard key={approval.request_id} approval={approval} onDecide={decide} />
            ))}

            {running && !streaming && approvals.length === 0 && (
              <div className="thinking"><span /><span /><span /></div>
            )}
          </div>

          {error && (
            <div className="error-bar">
              <span>{error}</span>
              <button onClick={() => setError(null)}>×</button>
            </div>
          )}

          <div className="composer">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={onKeyDown}
              placeholder={running ? '运行中：输入以插话（steer）…' : '输入消息，Enter 发送，Shift+Enter 换行'}
              rows={1}
            />
            <div className="composer-actions">
              <span className={`status-pill ${running ? 'busy' : ''}`}>{status}</span>
              {running ? (
                <button className="btn danger" onClick={stop}>停止</button>
              ) : (
                <button className="btn primary" onClick={submit} disabled={!input.trim()}>
                  发送
                </button>
              )}
            </div>
          </div>
        </section>

        <aside className="side-panel">
          <div className="side-card">
            <h3>Session</h3>
            <dl>
              <div><dt>provider</dt><dd>{provider}</dd></div>
              <div><dt>model</dt><dd>{model || '—'}</dd></div>
              <div><dt>status</dt><dd>{status}</dd></div>
              <div><dt>tokens</dt><dd>{usage.prompt_tokens + usage.completion_tokens}</dd></div>
            </dl>
          </div>
          <div className="side-card">
            <h3>快捷提示</h3>
            <p className="muted">`write_note` 会触发审批卡；`get_time` 直接执行。</p>
          </div>
          <div className="side-card">
            <h3>这一版</h3>
            <ul className="plain-list">
              <li>DeepSeek / fake 流式</li>
              <li>工具调用 + 审批</li>
              <li>WebSocket 断线重连</li>
              <li>会话暂存内存</li>
            </ul>
          </div>
        </aside>
      </main>
    </div>
  )
}
