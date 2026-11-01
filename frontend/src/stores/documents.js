/**
 * 知识库状态：文档列表 + processing 期间轮询。
 * 状态流转：processing → ready / empty / failed。
 */
import { defineStore } from 'pinia'

import { deleteDocument, listDocuments, retryDocument, uploadDocument } from '@/api/http'

const POLL_INTERVAL_MS = 3000

export const useDocumentsStore = defineStore('documents', {
  state: () => ({
    documents: [],
    timer: null,
  }),

  getters: {
    processing: (state) => state.documents.some((d) => d.status === 'processing'),
  },

  actions: {
    async loadDocuments() {
      this.documents = await listDocuments()
      if (this.processing) this.ensurePolling()
    },

    async upload(file, onUploadProgress) {
      const doc = await uploadDocument(file, onUploadProgress)
      this.documents.unshift(doc)
      this.ensurePolling()
      return doc
    },

    async remove(id) {
      await deleteDocument(id)
      this.documents = this.documents.filter((d) => d.id !== id)
    },

    // 重新解析失败文档：用后端返回的 processing 记录原位替换，并恢复轮询
    async retry(id) {
      const doc = await retryDocument(id)
      const index = this.documents.findIndex((d) => d.id === id)
      if (index !== -1) this.documents[index] = doc
      this.ensurePolling()
    },

    // 存在 processing 文档时启动 3s 轮询，全终态自动停止；幂等
    ensurePolling() {
      if (this.timer) return
      this.timer = setInterval(async () => {
        await this.loadDocuments()
        if (!this.processing) this.stopPolling()
      }, POLL_INTERVAL_MS)
    },

    stopPolling() {
      clearInterval(this.timer)
      this.timer = null
    },
  },
})
