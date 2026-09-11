<script setup>
// 消息流容器：渲染消息列表，新消息与 token 追加时自动贴底滚动
import { computed, nextTick, ref, watch } from 'vue'
import MessageItem from './MessageItem.vue'

const props = defineProps({
  messages: { type: Array, required: true },
  streaming: { type: Boolean, default: false },
})

const container = ref(null)

// 流式输出的始终是最后一条消息
const activeIndex = computed(() => (props.streaming ? props.messages.length - 1 : -1))

// 监听消息数量（新增/切换会话）与末条内容（token 追加）
watch(
  () => [props.messages.length, props.messages.at(-1)?.content],
  async () => {
    await nextTick()
    if (container.value) container.value.scrollTop = container.value.scrollHeight
  },
)
</script>

<template>
  <div ref="container" class="msg-list">
    <div class="msg-list__inner">
      <MessageItem
        v-for="(message, index) in messages"
        :key="index"
        :message="message"
        :active="index === activeIndex"
      />
    </div>
  </div>
</template>

<style scoped>
.msg-list {
  height: 100%;
  overflow-y: auto;
}

.msg-list__inner {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
</style>
