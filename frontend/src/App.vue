<script setup>
import { ChatDotRound, Collection } from '@element-plus/icons-vue'
</script>

<template>
  <el-container class="shell">
    <el-aside width="220px" class="shell__aside">
      <div class="shell__logo">RAG 知识库助手</div>
      <el-menu router :default-active="$route.path" class="shell__menu">
        <el-menu-item index="/">
          <el-icon><ChatDotRound /></el-icon>
          <span>对话</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Collection /></el-icon>
          <span>知识库</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="shell__main">
      <router-view />
    </el-main>
  </el-container>
</template>

<style scoped>
.shell {
  height: 100vh;
}

.shell__aside {
  border-right: 1px solid var(--el-border-color-light);
}

.shell__logo {
  padding: 20px 16px;
  font-size: 16px;
  font-weight: 600;
}

.shell__menu {
  border-right: none;
}

.shell__main {
  padding: 0;
}
</style>

<style>
/* 全局基础样式 */
html,
body {
  margin: 0;
  height: 100%;
}

#app {
  height: 100%;
}
</style>
