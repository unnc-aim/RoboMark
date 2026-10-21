<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "../stores/user";
import { message } from "../shared/ui/feedback";
const router = useRouter(),
  user = useUserStore();
let saved = {};
try {
  saved = JSON.parse(
    localStorage.getItem("robomark-workspace-preferences") || "{}",
  );
} catch {}
const form = ref({
  name: "AIM 视觉工作空间",
  description: "为 RoboMaster 机器人视觉准备可靠的检测数据。",
  ...saved,
});
function save() {
  localStorage.setItem(
    "robomark-workspace-preferences",
    JSON.stringify(form.value),
  );
  window.dispatchEvent(new Event("workspace-preferences"));
  message.success("本机工作空间偏好已保存");
}
</script>
<template>
  <header class="page-heading">
    <div>
      <h1>工作空间设置</h1>
      <p>让团队的标注环境清晰、稳定。</p>
    </div>
  </header>
  <div class="two-column">
    <ui-card class="panel-padding"
      ><div class="section-heading"><h2>工作空间信息</h2></div>
      <ui-alert title="本机显示偏好" :closable="false"
        >名称和说明保存在当前浏览器中。</ui-alert
      ><ui-form @submit.prevent="save"
        ><ui-form-item label="工作空间名称"
          ><ui-input
            v-model="form.name"
            required
            maxlength="60" /></ui-form-item
        ><ui-form-item label="团队说明"
          ><ui-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            maxlength="500"
        /></ui-form-item>
        <div class="form-grid">
          <ui-form-item label="语言"
            ><ui-input model-value="简体中文" disabled /></ui-form-item
          ><ui-form-item label="显示主题"
            ><ui-input model-value="管理页浅色 / 工作台深色" disabled
          /></ui-form-item>
        </div>
        <ui-button type="primary" native-type="submit" icon="Save"
          >保存更改</ui-button
        ></ui-form
      ></ui-card
    >
    <div class="stack">
      <ui-card class="panel-padding"
        ><div class="section-heading"><h2>访问与账号</h2></div>
        <div class="settings-links">
          <ui-button
            v-if="user.isAdmin"
            variant="ghost"
            icon="Users"
            @click="router.push('/admin/users')"
            >管理工作空间成员 <ui-icon name="ArrowRight" /></ui-button
          ><ui-button
            variant="ghost"
            icon="Server"
            @click="router.push('/profiles')"
            >管理推理接口 <ui-icon name="ArrowRight" /></ui-button
          ><ui-button
            variant="ghost"
            icon="BookOpen"
            @click="router.push('/tutorial')"
            >查看使用教程 <ui-icon name="ArrowRight"
          /></ui-button></div></ui-card
      ><ui-card class="panel-padding"
        ><div class="section-heading"><h2>当前账号</h2></div>
        <p class="account-name">{{ user.user?.username }}</p>
        <p class="form-tip">
          {{ user.isAdmin ? "管理员" : "标注员" }} ·
          {{ user.user?.email || "未填写邮箱" }}
        </p></ui-card
      >
    </div>
  </div>
</template>
<style scoped>
.settings-links {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.settings-links .ui-button {
  justify-content: flex-start;
  padding: 12px 0;
}
.settings-links .ui-button > svg:last-child {
  margin-left: auto;
}
.account-name {
  margin-bottom: 10px;
  font-size: 18px;
}
</style>
