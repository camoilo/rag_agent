<script setup>
// 知识库页：统计卡片、上传、文档列表
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
    <h2>知识库</h2>
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
