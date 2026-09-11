<script setup>
// 聊天页：左侧会话列表 + 右侧消息流与输入区
import SessionList from '@/components/chat/SessionList.vue'
import MessageList from '@/components/chat/MessageList.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()

// 无会话时先自动新建，再发送
async function handleSend(question) {
  try {
    if (!chat.currentSessionId) await chat.newSession()
    await chat.sendQuestion(question)
  } catch {
    // 失败提示已由 http 拦截器统一弹出
  }
}
</script>

<template>
  <div class="chat">
    <aside class="chat__aside">
      <SessionList />
    </aside>

    <section class="chat__body">
      <header class="chat__header">
        {{ chat.currentSession?.title ?? '对话' }}
      </header>

      <main v-loading="chat.loadingMessages" class="chat__main">
        <div v-if="!chat.currentSessionId" class="chat__empty">
          <el-empty description="点击左侧「新建对话」开始提问" />
        </div>
        <MessageList v-else :messages="chat.messages" :streaming="chat.streaming" />
      </main>

      <footer class="chat__footer">
        <ChatInput :streaming="chat.streaming" @send="handleSend" @stop="chat.stopStreaming" />
      </footer>
    </section>
  </div>
</template>

<style scoped>
.chat {
  display: flex;
  height: 100%;
}

.chat__aside {
  width: 240px;
  border-right: 1px solid var(--el-border-color-light);
}

.chat__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.chat__header {
  height: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--el-border-color-light);
  font-weight: 600;
}

.chat__main {
  flex: 1;
  min-height: 0;
}

.chat__empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat__footer {
  flex-shrink: 0;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-light);
}
</style>
