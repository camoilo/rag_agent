<script setup>
// 知识库页：统计卡片 + 上传卡片 + 文档表格
// 统计随文档状态变化（上传 / 轮询 processing→ready / 删除）自动刷新
import { onMounted, ref, watch } from 'vue'
import StatsCards from '@/components/knowledge/StatsCards.vue'
import UploadCard from '@/components/knowledge/UploadCard.vue'
import DocumentTable from '@/components/knowledge/DocumentTable.vue'
import { getStats } from '@/api/http'
import { useDocumentsStore } from '@/stores/documents'

const documentsStore = useDocumentsStore()
const stats = ref(null)

async function loadStats() {
  stats.value = await getStats()
}

onMounted(() => {
  documentsStore.loadDocuments()
  loadStats()
})

// 文档状态变化（上传入列 / 轮询 processing→ready / 删除）时同步刷新统计
watch(
  () => documentsStore.documents.map((d) => d.status).join(','),
  () => loadStats(),
)
</script>

<template>
  <section class="knowledge">
    <StatsCards :stats="stats" />

    <div class="knowledge__upload">
      <UploadCard :upload="documentsStore.upload" />
    </div>

    <div class="knowledge__table">
      <DocumentTable :documents="documentsStore.documents" />
    </div>
  </section>
</template>

<style scoped>
.knowledge {
  padding: 24px;
  max-width: 1100px;
  margin: 0 auto;
  overflow-y: auto;
  height: 100%;
  box-sizing: border-box;
}

.knowledge__upload {
  margin-top: 20px;
}

.knowledge__table {
  margin-top: 20px;
}
</style>
