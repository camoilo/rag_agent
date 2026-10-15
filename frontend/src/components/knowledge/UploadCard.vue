<script setup>
// 上传卡片：拖拽 / 点击选择，前端校验（类型、大小、空文件）+ 逐文件进度条
// upload 为父级传入的 store action：(file, onUploadProgress) => Promise
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  upload: { type: Function, required: true },
})

// 后端按当前解析模式校验，此处为 MinerU 各模式支持格式的并集
const ALLOWED_SUFFIXES = [
  '.pdf',
  '.txt',
  '.md',
  '.doc',
  '.docx',
  '.ppt',
  '.pptx',
  '.xls',
  '.xlsx',
  '.html',
  '.png',
  '.jpg',
  '.jpeg',
  '.jp2',
  '.webp',
  '.gif',
  '.bmp',
]
const MAX_SIZE_BYTES = 200 * 1024 * 1024
const MAX_SIZE_MB = MAX_SIZE_BYTES / (1024 * 1024)

// 本地上传任务列表：{ name, percent }，上传期间显示进度条
const tasks = ref([])

function validate(file) {
  const name = file.name.toLowerCase()
  if (!ALLOWED_SUFFIXES.some((s) => name.endsWith(s))) {
    ElMessage.error(`「${file.name}」不支持的格式，仅支持 ${ALLOWED_SUFFIXES.join(' / ')}`)
    return false
  }
  if (file.size === 0) {
    ElMessage.error(`「${file.name}」是空文件`)
    return false
  }
  if (file.size > MAX_SIZE_BYTES) {
    ElMessage.error(`「${file.name}」超过 ${MAX_SIZE_MB}MB 上限`)
    return false
  }
  return true
}

// el-upload 逐文件调用；返回 Promise 供其跟踪状态（show-file-list 已关闭，仅用进度）
async function handleUpload({ file }) {
  if (!validate(file)) return
  const task = { name: file.name, percent: 0 }
  tasks.value.push(task)
  try {
    await props.upload(file, (event) => {
      if (event.total) task.percent = Math.round((event.loaded / event.total) * 100)
    })
  } finally {
    tasks.value = tasks.value.filter((t) => t !== task)
  }
}
</script>

<template>
  <div class="upload">
    <el-upload
      drag
      multiple
      :accept="ALLOWED_SUFFIXES.join(',')"
      :show-file-list="false"
      :http-request="handleUpload"
    >
      <div class="upload__zone">
        <el-icon :size="36" class="upload__icon"><UploadFilled /></el-icon>
        <p class="upload__text">拖拽文件到此处，或点击选择</p>
        <p class="upload__hint">
          支持 PDF / Office 文档 / 图片 / txt / md，单个不超过 {{ MAX_SIZE_MB }}MB
        </p>
      </div>
    </el-upload>

    <div v-for="task in tasks" :key="task.name" class="upload__task">
      <span class="upload__name">{{ task.name }}</span>
      <el-progress :percentage="task.percent" :stroke-width="8" class="upload__progress" />
    </div>
  </div>
</template>

<style scoped>
.upload__zone {
  padding: 12px 0;
}

.upload__icon {
  color: var(--el-text-color-secondary);
}

.upload__text {
  margin: 8px 0 4px;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.upload__hint {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.upload__task {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
}

.upload__name {
  flex-shrink: 0;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.upload__progress {
  flex: 1;
}
</style>
