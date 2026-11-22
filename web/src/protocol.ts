export type JsonRpcId = string | number

export type JsonRpcError = {
  code: number
  message: string
  data?: unknown
}

export type JsonRpcRequest = {
  jsonrpc: '2.0'
  id: JsonRpcId
  method: string
  params: Record<string, unknown>
}

export type JsonRpcResponse = {
  jsonrpc: '2.0'
  id: JsonRpcId | null
  result?: unknown
  error?: JsonRpcError
}

export type JsonRpcNotification = {
  jsonrpc: '2.0'
  method: string
  params?: Record<string, unknown>
}

export type ServerEnvelope = JsonRpcResponse | JsonRpcNotification

export type ApprovalRequest = {
  request_id: string
  run_id: string
  tool_name: string
  tool_call_id: string
  arguments: Record<string, unknown>
  reason: string
  options: string[]
}

export type Usage = {
  prompt_tokens: number
  completion_tokens: number
}
