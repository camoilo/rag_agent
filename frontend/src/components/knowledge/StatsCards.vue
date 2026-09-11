<script setup>
// 统计卡片：展示 /api/stats 的使用指标
import { ChatDotRound, Collection, Document, Message, Upload } from '@element-plus/icons-vue'

defineProps({
  stats: { type: Object, default: null },
})

// 卡片定义：字段名对应后端 stats 响应
const cards = [
  { key: 'sessions', label: '会话数', icon: ChatDotRound },
  { key: 'documents', label: '文档数', icon: Collection },
  { key: 'ready_documents', label: '就绪文档', icon: Document },
  { key: 'messages', label: '消息数', icon: Message },
  { key: 'prompt_tokens', label: '输入 tokens', icon: Upload },
  { key: 'completion_tokens', label: '输出 tokens', icon: Upload },
]
</script>

<template>
  <div class="stats">
    <div v-for="card in cards" :key="card.key" class="stats__card">
      <div class="stats__label">
        <el-icon :size="14"><component :is="card.icon" /></el-icon>
        {{ card.label }}
      </div>
      <div class="stats__value">{{ stats?.[card.key] ?? '—' }}</div>
    </div>
  </div>
</template>

<style scoped>
.stats {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}

/* 中屏 3 列，小屏 2 列 */
@media (max-width: 1100px) {
  .stats {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 640px) {
  .stats {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stats__card {
  padding: 14px 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.stats__label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.stats__value {
  margin-top: 6px;
  font-size: 22px;
  font-weight: 600;
  line-height: 1;
}
</style>
