/**
 * 聊天状态：会话列表 / 当前会话 / 消息 / 流式状态。
 * 消息结构（前端统一形态）：
 * - role: 'user' | 'assistant'
 * - content: 正文
 * - citations: [{ index, source, snippet }]
 * - stats: 流式会话独有 { prompt_tokens, completion_tokens, elapsed_ms }（历史消息无）
 * - error: 流内错误信息（红字气泡）
 */
import { defineStore } from 'pinia'

import {
  createSession,
  deleteSession,
  listMessages,
  listSessions,
  renameSession,
} from '@/api/http'
import { streamChat } from '@/api/sse'

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessions: [],
    currentSessionId: null,
    messages: [],
    loadingMessages: false, // 历史消息加载中
    streaming: false,
    abortController: null,
  }),

  getters: {
    currentSession: (state) =>
      state.sessions.find((s) => s.id === state.currentSessionId) ?? null,
  },

  actions: {
    async loadSessions() {
      this.sessions = await listSessions()
    },

    async newSession() {
      const session = await createSession()
      this.sessions.unshift(session)
      await this.selectSession(session.id)
      return session
    },

    async selectSession(id) {
      this.currentSessionId = id
      this.loadingMessages = true
      try {
        this.messages = await listMessages(id)
      } finally {
        this.loadingMessages = false
      }
    },

    async renameSession(id, title) {
      const updated = await renameSession(id, title)
      const index = this.sessions.findIndex((s) => s.id === id)
      if (index !== -1) this.sessions[index] = updated
    },

    async removeSession(id) {
      await deleteSession(id)
      this.sessions = this.sessions.filter((s) => s.id !== id)
      if (this.currentSessionId === id) {
        this.currentSessionId = null
        this.messages = []
      }
    },

    async sendQuestion(question) {
      if (!this.currentSessionId || this.streaming) return
      const sessionId = this.currentSessionId

      this.messages.push({ role: 'user', content: question, citations: [] })
      this.messages.push({ role: 'assistant', content: '', citations: [], stats: null })
      // 从响应式数组取回代理引用：token 追加需触发视图更新
      const assistant = this.messages[this.messages.length - 1]

      this.streaming = true
      this.abortController = new AbortController()
      try {
        await streamChat({
          sessionId,
          question,
          onToken: (content) => {
            assistant.content += content
          },
          onDone: (event) => {
            assistant.citations = event.citations
            assistant.stats = {
              prompt_tokens: event.prompt_tokens,
              completion_tokens: event.completion_tokens,
              elapsed_ms: event.elapsed_ms,
            }
          },
          onError: (detail) => {
            assistant.error = detail
          },
          signal: this.abortController.signal,
        })
        // 首条消息会成为会话标题，静默刷新列表同步显示
        await this.loadSessions()
      } catch (err) {
        if (err.name !== 'AbortError') assistant.error = err.message ?? String(err)
      } finally {
        this.streaming = false
        this.abortController = null
      }
    },

    stopStreaming() {
      this.abortController?.abort()
    },
  },
})
