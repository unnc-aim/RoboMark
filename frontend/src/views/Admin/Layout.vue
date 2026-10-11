<script setup>
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../../stores/user'
import { computed } from 'vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const adminMenuItems = [
  { path: '/admin', icon: 'DataAnalysis', title: '仪表盘' },
  { path: '/admin/datasets', icon: 'Folder', title: '数据集管理' },
  { path: '/admin/users', icon: 'User', title: '用户管理' },
  { path: '/admin/statistics', icon: 'PieChart', title: '工作量统计' },
  { path: '/admin/export', icon: 'Download', title: '数据导出' }
]
const preannotationPath = computed(() => route.params.datasetId
  ? router.resolve({ name: 'Preannotation', params: { datasetId: route.params.datasetId } }).path
  : '/')
const menuItems = computed(() => userStore.isAdmin ? adminMenuItems : [
  { path: '/', icon: 'House', title: '数据集' },
  ...(route.params.datasetId ? [{ path: preannotationPath.value, icon: 'MagicStick', title: '预标注与审核' }] : []),
  { path: '/tutorial', icon: 'Guide', title: '使用教程' }
])
const activeMenu = computed(() => userStore.isAdmin
  ? route.meta.activeMenu || route.path
  : preannotationPath.value)
const pageTitle = computed(() => route.meta.title || adminMenuItems.find(m => m.path === route.path)?.title || route.name)
// 同一数据集的图片导航保留审核状态；切换数据集 / 批次时重新初始化页面。
const viewKey = computed(() => `${route.name}:${route.params.datasetId || ''}:${route.params.taskId || ''}`)

async function handleLogout() {
  if (route.name === 'PreannotationReview') {
    // 先让审核页处理未保存草稿，确认离开后再清除登录凭据。
    const failure = await router.push('/')
    if (failure) return
  }
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="admin-layout" :class="{ 'workspace-layout': route.meta.activeMenu === '/admin/datasets' }">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <h2>RoboMark</h2>
        <span>{{ userStore.isAdmin ? '管理后台' : '标注工作台' }}</span>
        <el-button v-if="userStore.isAdmin" type="primary" link @click="router.push('/')">
          首页
        </el-button>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
          :aria-label="item.title"
          :title="item.title"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <el-button type="primary" link @click="router.push('/')">
          <el-icon><Back /></el-icon> 返回首页
        </el-button>
      </div>
    </el-aside>

    <el-container class="admin-content">
      <el-header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: userStore.isAdmin ? '/admin' : '/' }">{{ userStore.isAdmin ? '管理后台' : '数据集' }}</el-breadcrumb-item>
            <el-breadcrumb-item v-if="userStore.isAdmin && route.meta.activeMenu === '/admin/datasets'" :to="{ path: '/admin/datasets' }">数据集管理</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.name === 'PreannotationReview'" :to="{ name: 'Preannotation', params: { datasetId: route.params.datasetId }, query: { task: route.params.taskId } }">预标注与审核</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.name !== 'AdminDashboard'">
              {{ pageTitle }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <span class="username">{{ userStore.user?.username }}</span>
          <el-button type="danger" link @click="handleLogout">
            退出登录
          </el-button>
        </div>
      </el-header>

      <el-main class="main">
        <router-view :key="viewKey" />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.admin-layout {
  min-height: 100vh;
}

.sidebar {
  background: #304156;
  display: flex;
  flex-direction: column;
}

.logo {
  padding: 20px;
  text-align: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo h2 {
  color: white;
  margin: 0;
  font-size: 18px;
}

.logo span {
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
}

.sidebar-menu {
  flex: 1;
  border: none;
  background: transparent;
}

.sidebar-menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.7);
}

.sidebar-menu :deep(.el-menu-item:hover),
.sidebar-menu :deep(.el-menu-item.is-active) {
  background: #263445;
  color: #409eff;
}

.sidebar-footer {
  padding: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.sidebar-footer .el-button {
  color: rgba(255, 255, 255, 0.7);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  border-bottom: 1px solid #eee;
  padding: 0 20px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.username {
  color: #666;
}

.main {
  background: #f5f7fa;
  padding: 20px;
  min-width: 0;
}

.admin-content { min-width: 0; }

@media (max-width: 650px) {
  .workspace-layout .sidebar { width: 64px !important; }
  .workspace-layout .logo { padding: 14px 4px; }
  .workspace-layout .logo h2 { font-size: 11px; }
  .workspace-layout .logo span, .workspace-layout .logo .el-button, .workspace-layout .sidebar-menu :deep(.el-menu-item span), .workspace-layout .sidebar-footer { display: none; }
  .workspace-layout .sidebar-menu :deep(.el-menu-item) { padding: 0 20px !important; }
  .workspace-layout .header { padding: 0 12px; height: auto; min-height: 60px; gap: 10px; }
  .workspace-layout .header-left { min-width: 0; }
  .workspace-layout .header-left :deep(.el-breadcrumb) { line-height: 1.7; }
  .workspace-layout .header-right { gap: 8px; flex-shrink: 0; }
  .workspace-layout .username { display: none; }
  .workspace-layout .main { padding: 12px; }
}
</style>
