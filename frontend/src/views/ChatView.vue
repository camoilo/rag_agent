<script setup>
// 聊天页：会话列表、消息流、输入框与 SSE 流式渲染
import { ref, onMounted } from 'vue'

const healthy = ref(false)

onMounted(async () => {
  try {
    const res = await fetch('/api/health')
    healthy.value = res.ok
  } catch {
    healthy.value = false
  }
})
</script>

<template>
  <section class="page">
    <h2>对话</h2>
    <p class="page__hint">
      后端连接：
      <el-tag :type="healthy ? 'success' : 'danger'" size="small">
        {{ healthy ? '正常' : '不可用' }}
      </el-tag>
    </p>
  </section>
</template>

<style scoped>
.page {
  padding: 24px;
}

.page__hint {
  color: var(--el-text-color-secondary);
}
</style>
