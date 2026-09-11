<script setup>
// 会话列表：新建 / 切换 / 重命名 / 删除
import { onMounted } from 'vue'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()

onMounted(() => chat.loadSessions())

async function handleNew() {
  try {
    await chat.newSession()
  } catch {
    // 失败提示已由 http 拦截器统一弹出
  }
}

async function handleRename(session) {
  try {
    const { value } = await ElMessageBox.prompt('会话标题', '重命名会话', {
      inputValue: session.title,
      inputPattern: /^.{1,30}$/,
      inputErrorMessage: '标题长度需为 1~30 个字符',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    const title = value.trim()
    if (title) await chat.renameSession(session.id, title)
  } catch {
    // 用户取消
  }
}

async function handleRemove(session) {
  try {
    await ElMessageBox.confirm(
      `确定删除会话「${session.title}」吗？删除后不可恢复。`,
      '删除会话',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await chat.removeSession(session.id)
  } catch {
    // 用户取消
  }
}
</script>

<template>
  <div class="sessions">
    <div class="sessions__top">
      <el-button type="primary" class="sessions__new" :icon="Plus" @click="handleNew">
        新建对话
      </el-button>
    </div>

    <div class="sessions__list">
      <div
        v-for="session in chat.sessions"
        :key="session.id"
        class="sessions__item"
        :class="{ 'is-active': session.id === chat.currentSessionId }"
        @click="chat.selectSession(session.id)"
      >
        <span class="sessions__title">{{ session.title }}</span>
        <span class="sessions__ops" @click.stop>
          <el-button link :icon="Edit" @click="handleRename(session)" />
          <el-button link type="danger" :icon="Delete" @click="handleRemove(session)" />
        </span>
      </div>
      <el-empty v-if="chat.sessions.length === 0" description="暂无会话" :image-size="60" />
    </div>
  </div>
</template>

<style scoped>
.sessions {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sessions__top {
  padding: 12px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.sessions__new {
  width: 100%;
}

.sessions__list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.sessions__item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.sessions__item:hover {
  background: var(--el-fill-color-light);
}

.sessions__item.is-active {
  background: var(--el-color-primary-light-9);
}

.sessions__title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

/* 操作按钮常显但弱化，悬停时高亮：位置固定、不跳版 */
.sessions__ops {
  display: inline-flex;
  opacity: 0.35;
}

.sessions__item:hover .sessions__ops {
  opacity: 1;
}
</style>
