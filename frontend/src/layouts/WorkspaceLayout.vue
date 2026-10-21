<script setup>
import { computed, ref, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useUserStore } from "../stores/user";
import BrandLogo from "../components/BrandLogo.vue";
const route = useRoute(),
  router = useRouter(),
  user = useUserStore();
const navigationOpen = ref(false),
  searchOpen = ref(false),
  search = ref("");
const links = computed(() => [
  { path: "/", title: "标注首页", icon: "House" },
  ...(user.isAdmin
    ? [{ path: "/admin", title: "管理概览", icon: "DataAnalysis" }]
    : []),
  ...(user.isAdmin
    ? [{ path: "/admin/datasets", title: "数据集", icon: "Folder" }]
    : []),
  ...(user.isAdmin
    ? [
        { path: "/admin/users", title: "工作空间成员", icon: "Users" },
        { path: "/admin/export", title: "数据导出", icon: "Download" },
      ]
    : []),
  { path: "/profiles", title: "推理接口", icon: "Server" },
  { path: "/tutorial", title: "使用教程与快捷键", icon: "BookOpen" },
]);
const active = computed(() =>
  route.path.startsWith("/datasets/") ||
  route.path.startsWith("/admin/categories")
    ? user.isAdmin
      ? "/admin/datasets"
      : "/"
    : route.path,
);
const title = computed(() =>
  [
    "DatasetDetail",
    "Preannotation",
    "AdminCategories",
    "DatasetSettings",
  ].includes(String(route.name))
    ? "数据集"
    : route.meta.title ||
      links.value.find((l) => l.path === active.value)?.title ||
      "工作空间",
);
function navigate(path) {
  navigationOpen.value = false;
  searchOpen.value = false;
  router.push(path);
}
function logout() {
  user.logout();
  router.push("/login");
}
function keydown(e) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    searchOpen.value = !searchOpen.value;
  }
}
onMounted(() => {
  window.addEventListener("keydown", keydown);
});
onUnmounted(() => {
  window.removeEventListener("keydown", keydown);
});
</script>
<template>
  <div class="workspace-shell" :class="{ 'navigation-open': navigationOpen }">
    <aside class="workspace-sidebar">
      <ui-button
        variant="ghost"
        class="workspace-brand"
        aria-label="返回标注首页"
        @click="navigate('/')"
        ><BrandLogo /><strong>RoboMark<span>.</span></strong></ui-button
      >
      <nav class="workspace-nav" aria-label="工作空间导航">
        <ui-button
          v-for="(link, index) in links"
          :key="index"
          variant="ghost"
          :class="{
            active: active === link.path && (link.path !== '/' || index === 0),
            'navigation-section-start': link.path === '/profiles',
          }"
          :aria-current="active === link.path ? 'page' : undefined"
          @click="navigate(link.path)"
          ><ui-icon :name="link.icon" /><span>{{ link.title }}</span></ui-button
        >
      </nav>
      <div class="sidebar-note">
        <ui-icon name="Layers" />
        <p>让每一帧，都有价值。<small>为可靠的视觉数据而设计。</small></p>
      </div>
      <div class="workspace-account">
        <span class="account-avatar">{{
          user.user?.username?.slice(0, 2).toUpperCase()
        }}</span>
        <div>
          <strong>{{ user.user?.username }}</strong
          ><small>{{ user.isAdmin ? "管理员" : "标注员" }}</small>
        </div>
        <ui-button variant="ghost" circle aria-label="退出登录" @click="logout"
          ><ui-icon name="LogOut"
        /></ui-button>
      </div>
    </aside>
    <ui-button
      v-if="navigationOpen"
      class="navigation-scrim"
      aria-label="关闭导航"
      @click="navigationOpen = false"
    />
    <div class="workspace-body">
      <header class="workspace-topbar">
        <div class="breadcrumb">
          <ui-button
            class="mobile-navigation"
            variant="ghost"
            circle
            aria-label="打开导航"
            :aria-expanded="navigationOpen"
            @click="navigationOpen = !navigationOpen"
            ><ui-icon name="PanelLeft" /></ui-button
          ><span>工作空间</span><span>/</span><strong>{{ title }}</strong>
        </div>
        <ui-button
          variant="ghost"
          class="workspace-search"
          @click="searchOpen = true"
          ><ui-icon name="Search" /><span>搜索页面与功能</span
          ><ui-kbd>⌘ K</ui-kbd></ui-button
        >
      </header>
      <main class="workspace-main"><slot /></main>
    </div>
    <ui-dialog v-model="searchOpen" title="搜索工作空间" width="500px"
      ><ui-input
        v-model="search"
        placeholder="搜索页面与功能"
        prefix-icon="Search" />
      <div class="search-links">
        <ui-button
          v-for="link in links.filter((l) => l.title.includes(search))"
          :key="link.title"
          variant="ghost"
          @click="navigate(link.path)"
          ><ui-icon :name="link.icon" />{{ link.title }}</ui-button
        ><ui-empty
          v-if="!links.some((l) => l.title.includes(search))"
          description="没有匹配的页面"
        /></div
    ></ui-dialog>
  </div>
</template>
<style scoped>
.workspace-shell {
  display: flex;
  min-height: calc(100dvh - 55px);
  background: var(--background);
}
.workspace-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: 224px;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-right: 1px solid var(--border);
  z-index: 50;
  padding: 25px 16px 15px;
}
.workspace-brand {
  justify-content: flex-start;
  gap: 8px;
  min-height: 39px;
  padding: 4px 8px;
  margin: -4px 0 21px;
  color: var(--foreground);
}
.workspace-brand :deep(.brand-logo) {
  width: 52px;
}
.workspace-brand strong {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -1px;
}
.workspace-brand strong > span {
  color: var(--primary);
}
.account-avatar {
  display: grid;
  place-items: center;
  width: 31px;
  height: 31px;
  background: #eef1f9;
  border: 1px solid var(--border);
  border-radius: 7px;
  color: #53617b;
  font-size: 10px;
  font-weight: 650;
  flex-shrink: 0;
}
.workspace-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.workspace-nav .ui-button {
  justify-content: flex-start;
  gap: 12px;
  border-radius: 7px;
  padding: 11px 13px;
  font-size: 12px;
  color: #777f8f;
  min-height: 39px;
}
.workspace-nav .active {
  background: #edf1ff;
  color: var(--primary);
  font-weight: 600;
}
.workspace-nav .navigation-section-start {
  margin-top: 22px;
}
.sidebar-note {
  margin: auto 7px 20px;
  padding-top: 40px;
  display: flex;
  gap: 9px;
  font-size: 10px;
  color: #8c94a2;
  line-height: 1.8;
}
.sidebar-note small {
  display: block;
  font-size: 9px;
}
.sidebar-note svg {
  margin-top: 2px;
  width: 15px;
}
.workspace-account {
  display: flex;
  align-items: center;
  gap: 9px;
  padding-top: 15px;
  border-top: 1px solid var(--border);
}
.account-avatar {
  background: #e9edfc;
  color: var(--primary);
}
.workspace-account strong {
  display: block;
  font-size: 11px;
}
.workspace-account small {
  display: block;
  color: var(--muted);
  font-size: 10px;
  margin-top: 4px;
}
.workspace-account > .ui-button {
  margin-left: auto;
}
.workspace-body {
  flex: 1;
  min-width: 0;
  margin-left: 224px;
}
.workspace-topbar {
  height: 64px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 34px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 13px;
  font-size: 11px;
  color: #8a92a2;
}
.breadcrumb strong {
  color: var(--foreground);
  font-weight: 500;
}
.workspace-search {
  font-size: 11px;
  gap: 10px;
  color: #969dac;
}
.workspace-main {
  padding: 34px;
  max-width: 1700px;
  margin: 0 auto;
  min-width: 0;
}
.mobile-navigation {
  display: none;
}
.navigation-scrim {
  display: none;
}
.search-links {
  display: flex;
  flex-direction: column;
  margin-top: 18px;
}
.search-links .ui-button {
  justify-content: flex-start;
  padding: 12px;
}
.search-links .ui-icon {
  margin-right: 8px;
}
@media (min-width: 1700px) {
  .workspace-main {
    padding: 40px 50px;
  }
}
@media (max-width: 1000px) {
  .workspace-sidebar {
    width: 195px;
    padding: 22px 12px;
  }
  .workspace-body {
    margin-left: 195px;
  }
  .workspace-main {
    padding: 25px;
  }
  .workspace-topbar {
    padding: 0 24px;
  }
  .workspace-search > span,
  .workspace-search .ui-kbd {
    display: none;
  }
}
@media (max-width: 700px) {
  .workspace-sidebar {
    transform: translateX(-100%);
    transition: transform 0.2s;
    width: 224px;
  }
  .navigation-open .workspace-sidebar {
    transform: translateX(0);
  }
  .workspace-body {
    margin-left: 0;
  }
  .workspace-main {
    padding: 22px 16px;
  }
  .workspace-topbar {
    height: 56px;
    padding: 0 14px;
  }
  .mobile-navigation {
    display: inline-flex;
  }
  .navigation-scrim {
    position: fixed;
    inset: 0;
    display: block;
    z-index: 49;
    background: #14203970;
    border: 0;
    border-radius: 0;
  }
  .workspace-shell {
    min-height: calc(100dvh - 85px);
  }
}
</style>
