<script setup>
// 输入区：Enter 发送（Shift+Enter 换行，输入法选词不触发），流式中按钮变"停止"
import { ref } from 'vue'

const props = defineProps({
  streaming: { type: Boolean, default: false },
})
const emit = defineEmits(['send', 'stop'])

const draft = ref('')

function submit() {
  const question = draft.value.trim()
  if (!question || props.streaming) return
  emit('send', question)
  draft.value = ''
}

function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="input">
    <el-input
      v-model="draft"
      type="textarea"
      :rows="3"
      resize="none"
      placeholder="输入问题，Enter 发送 / Shift + Enter 换行"
      @keydown="onKeydown"
    />
    <div class="input__bar">
      <span class="input__hint">回答由 AI 生成，仅供参考</span>
      <el-button v-if="streaming" type="danger" plain @click="emit('stop')">停止</el-button>
      <el-button v-else type="primary" :disabled="!draft.trim()" @click="submit">发送</el-button>
    </div>
  </div>
</template>

<style scoped>
.input {
  max-width: 892px; /* 与消息区内容宽度对齐（860 + 两侧 16 padding） */
  margin: 0 auto;
  padding: 0 16px;
  width: 100%;
  box-sizing: border-box;
}

.input__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.input__hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
