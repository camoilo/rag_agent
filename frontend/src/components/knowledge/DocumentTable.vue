<script setup>
// 文档表格：状态 tag / 失败原因 tooltip / 删除确认
import { ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import { useDocumentsStore } from '@/stores/documents'

defineProps({
  documents: { type: Array, required: true },
})

const documentsStore = useDocumentsStore()

// 状态 → tag 类型与文案
const STATUS_MAP = {
  processing: { type: 'warning', label: '解析中' },
  ready: { type: 'success', label: '已就绪' },
  empty: { type: 'info', label: '空文档' },
  failed: { type: 'danger', label: '失败' },
}

async function handleRemove(doc) {
  try {
    await ElMessageBox.confirm(
      `确定删除「${doc.document_name}」吗？其向量分块将一并清除。`,
      '删除文档',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await documentsStore.remove(doc.id)
  } catch {
    // 用户取消
  }
}
</script>

<template>
  <el-table :data="documents" empty-text="暂无文档，请先上传">
    <el-table-column label="文档名" min-width="220">
      <template #default="{ row }">
        <span class="doc-name">{{ row.document_name }}</span>
      </template>
    </el-table-column>

    <el-table-column label="状态" width="100" align="center">
      <template #default="{ row }">
        <!-- 失败时悬浮显示原因 -->
        <el-tooltip
          v-if="row.status === 'failed' && row.error"
          :content="row.error"
          placement="top"
        >
          <el-tag :type="STATUS_MAP[row.status]?.type ?? 'info'">
            {{ STATUS_MAP[row.status]?.label ?? row.status }}
          </el-tag>
        </el-tooltip>
        <el-tag v-else :type="STATUS_MAP[row.status]?.type ?? 'info'">
          {{ STATUS_MAP[row.status]?.label ?? row.status }}
        </el-tag>
      </template>
    </el-table-column>

    <el-table-column label="分块数" width="90" align="center">
      <template #default="{ row }">
        {{ row.status === 'processing' ? '—' : row.chunk_count }}
      </template>
    </el-table-column>

    <el-table-column prop="created_at" label="上传时间" width="180" />

    <el-table-column label="操作" width="80" align="center">
      <template #default="{ row }">
        <el-button link type="danger" :icon="Delete" @click="handleRemove(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<style scoped>
.doc-name {
  font-size: 14px;
}
</style>
