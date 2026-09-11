/**
 * REST API 封装：axios 实例 + 全部后端端点。
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api', timeout: 30000 })

// 统一错误提示：后端 FastAPI 错误体为 {detail: ...}
http.interceptors.response.use(
  (res) => res,
  (error) => {
    const detail = error.response?.data?.detail ?? error.message
    ElMessage.error(typeof detail === 'string' ? detail : '请求失败')
    return Promise.reject(error)
  },
)

// ---- 系统 ----
export const getHealth = () => http.get('/health').then((r) => r.data)
export const getStats = () => http.get('/stats').then((r) => r.data)

// ---- 会话 ----
export const listSessions = () => http.get('/sessions').then((r) => r.data)
export const createSession = () => http.post('/sessions').then((r) => r.data)
export const renameSession = (id, title) =>
  http.patch(`/sessions/${id}`, { title }).then((r) => r.data)
export const deleteSession = (id) => http.delete(`/sessions/${id}`)
export const listMessages = (sessionId) =>
  http.get(`/sessions/${sessionId}/messages`).then((r) => r.data)

// ---- 文档 ----
export const listDocuments = () => http.get('/documents').then((r) => r.data)
export const uploadDocument = (file) => {
  const form = new FormData()
  form.append('file', file)
  // 上传单独放宽超时（大文件 + 慢网络）
  return http.post('/documents', form, { timeout: 120000 }).then((r) => r.data)
}
export const deleteDocument = (id) => http.delete(`/documents/${id}`)
