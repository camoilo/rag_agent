<script setup>
// 单条消息：user 右侧气泡，assistant 左侧 Markdown 渲染；
// active 表示该条正处于流式输出（控制"思考中"提示与光标）
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { ChatDotRound, User } from '@element-plus/icons-vue'

const props = defineProps({
  message: { type: Object, required: true },
  active: { type: Boolean, default: false },
})

// 流式输出时 token 到达非常密集，逐字全量解析 Markdown 是 O(n²) 开销；
// 按固定间隔渲染最新内容，非流式或流结束时立即渲染
const RENDER_INTERVAL_MS = 120
const rendered = ref('')
let timer = null

function flush() {
  clearTimeout(timer)
  timer = null
  rendered.value = props.message.content ?? ''
}

watch(
  () => props.message.content,
  () => {
    if (!props.active) return flush()
    if (!timer) timer = setTimeout(flush, RENDER_INTERVAL_MS)
  },
  { immediate: true },
)

// 流式结束/停止时补齐最后一帧
watch(
  () => props.active,
  (active) => {
    if (!active) flush()
  },
)

onBeforeUnmount(() => clearTimeout(timer))

const html = computed(() => DOMPurify.sanitize(marked.parse(rendered.value, { breaks: true })))
</script>

<template>
  <div class="item" :class="`item--${message.role}`">
    <el-avatar :size="32" class="item__avatar">
      <el-icon v-if="message.role === 'assistant'"><ChatDotRound /></el-icon>
      <el-icon v-else><User /></el-icon>
    </el-avatar>

    <!-- 用户消息：纯文本气泡 -->
    <div v-if="message.role === 'user'" class="item__bubble">{{ message.content }}</div>

    <!-- 助手消息：Markdown + 引用 + 用量 -->
    <div v-else class="item__body">
      <div v-if="message.content" class="markdown" v-html="html" />
      <span v-if="active && message.content" class="item__cursor" />
      <p v-if="active && !message.content && !message.error" class="item__thinking">思考中…</p>

      <div v-if="message.citations?.length" class="citations">
        <div class="citations__title">引用来源</div>
        <div v-for="c in message.citations" :key="c.index" class="citations__row">
          <span class="citations__source">
            [{{ c.index }}] {{ c.source }}
          </span>
          <span class="citations__snippet">{{ c.snippet }}</span>
        </div>
      </div>

      <div v-if="message.stats" class="item__stats">
        耗时 {{ message.stats.elapsed_ms }} ms · 输入 {{ message.stats.prompt_tokens }} tokens ·
        输出 {{ message.stats.completion_tokens }} tokens
      </div>

      <p v-if="message.error" class="item__error">{{ message.error }}</p>
    </div>
  </div>
</template>

<style scoped>
.item {
  display: flex;
  gap: 10px;
}

.item--user {
  flex-direction: row-reverse; /* 头像换到右侧，气泡靠右 */
}

.item__avatar {
  flex-shrink: 0;
}

.item__bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
  white-space: pre-wrap;
}

.item__body {
  min-width: 0;
  flex: 1;
}

.item__thinking {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.item__cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--el-color-primary);
  animation: cursor-blink 1s step-end infinite;
}

@keyframes cursor-blink {
  50% {
    opacity: 0;
  }
}

/* 引用列表 */
.citations {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}

.citations__title {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}

.citations__row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}

.citations__source {
  color: var(--el-text-color-primary);
}

.citations__snippet {
  color: var(--el-text-color-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item__stats {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.item__error {
  margin: 0;
  color: var(--el-color-danger);
  font-size: 14px;
}

/* Markdown 渲染样式（v-html 内容需用 :deep） */
.markdown {
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}

.markdown :deep(p) {
  margin: 0 0 8px;
}

.markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3),
.markdown :deep(h4) {
  margin: 16px 0 8px;
  line-height: 1.4;
}

.markdown :deep(h1) {
  font-size: 20px;
}

.markdown :deep(h2) {
  font-size: 17px;
}

.markdown :deep(h3),
.markdown :deep(h4) {
  font-size: 15px;
}

.markdown :deep(ul),
.markdown :deep(ol) {
  margin: 0 0 8px;
  padding-left: 20px;
}

.markdown :deep(li) {
  margin: 4px 0;
}

.markdown :deep(pre) {
  margin: 0 0 8px;
  padding: 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  overflow-x: auto;
}

.markdown :deep(code) {
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
}

.markdown :deep(pre code) {
  padding: 0;
  background: none;
}

.markdown :deep(:not(pre) > code) {
  padding: 2px 4px;
  border-radius: 3px;
  background: var(--el-fill-color);
}

.markdown :deep(table) {
  margin: 0 0 8px;
  border-collapse: collapse;
}

.markdown :deep(th),
.markdown :deep(td) {
  padding: 6px 10px;
  border: 1px solid var(--el-border-color-lighter);
}

.markdown :deep(blockquote) {
  margin: 0 0 8px;
  padding: 4px 12px;
  border-left: 3px solid var(--el-border-color);
  color: var(--el-text-color-secondary);
}

.markdown :deep(a) {
  color: var(--el-color-primary);
}
</style>
