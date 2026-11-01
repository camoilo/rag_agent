<script setup>
// 上传卡片：拖拽 / 点击选择，前端校验（类型、大小、空文件）+ 逐文件进度条
// upload 为父级传入的 store action：(file, onUploadProgress) => Promise
import { computed, onMounted, ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getUploadConfig } from '@/api/http'

const props = defineProps({
  upload: { type: Function, required: true },
})

// 上传约束由后端 /api/config 下发，随当前解析模式变化
const config = ref(null)
onMounted(async () => {
  try {
    config.value = await getUploadConfig()
  } catch {
    // 获取失败时退化为服务端校验（错误提示已由 http 拦截器处理）
  }
})

const accept = computed(() => config.value?.allowed_suffixes.join(',') ?? undefined)
const maxSizeMb = computed(() =>
  config.value ? Math.floor(config.value.max_upload_bytes / (1024 * 1024)) : null,
)

// 本地上传任务列表：{ name, percent }，上传期间显示进度条
const tasks = ref([])

function validate(file) {
  const name = file.name.toLowerCase()
  const rules = config.value
  if (rules && !rules.allowed_suffixes.some((s) => name.endsWith(s))) {
    ElMessage.error(`「${file.name}」不支持的格式，仅支持 ${rules.allowed_suffixes.join(' / ')}`)
    return false
  }
  if (file.size === 0) {
    ElMessage.error(`「${file.name}」是空文件`)
    return false
  }
  if (rules && file.size > rules.max_upload_bytes) {
    ElMessage.error(`「${file.name}」超过 ${maxSizeMb.value}MB 上限`)
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
      :accept="accept"
      :show-file-list="false"
      :http-request="handleUpload"
    >
      <div class="upload__zone">
        <el-icon :size="36" class="upload__icon"><UploadFilled /></el-icon>
        <p class="upload__text">拖拽文件到此处，或点击选择</p>
        <p class="upload__hint">
          支持 PDF / Office 文档 / 图片 / txt / md<template v-if="config">，单个不超过 {{ maxSizeMb }}MB、{{ config.max_pages }} 页</template>
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
