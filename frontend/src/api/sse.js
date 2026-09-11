/**
 * 聊天 SSE 流式请求。
 * POST 场景无法使用 EventSource，手写 fetch + ReadableStream 解析。
 *
 * 后端帧格式：`data: {json}\n\n`，事件类型：
 * - token { type, content }            正文增量，多次
 * - done  { type, citations, prompt_tokens, completion_tokens, elapsed_ms }
 * - error { type, detail }
 *
 * @param {object} options
 * @param {string} options.sessionId
 * @param {string} options.question
 * @param {(content: string) => void} [options.onToken]
 * @param {(event: object) => void} [options.onDone]
 * @param {(detail: string) => void} [options.onError]  流内 error 事件
 * @param {AbortSignal} [options.signal]                 中断流（调用方处理 AbortError）
 */
export async function streamChat({ sessionId, question, onToken, onDone, onError, signal }) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, question }),
    signal,
  })
  if (!res.ok) {
    const detail = await res
      .json()
      .then((body) => body.detail)
      .catch(() => null)
    throw new Error(detail ?? `请求失败（${res.status}）`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  // 逐块累积，按空行切帧；末帧可能不完整，留在 buffer 等下一块
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const line = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      if (!line.startsWith('data: ')) continue
      const event = JSON.parse(line.slice(6))
      if (event.type === 'token') onToken?.(event.content)
      else if (event.type === 'done') onDone?.(event)
      else if (event.type === 'error') onError?.(event.detail)
    }
  }
}
