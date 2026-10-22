<script setup>
import { ref, onMounted } from "vue";
import { useUserStore } from "../stores/user";
import api, { reportError } from "../utils/api";
import PreannotationProfileDialog from "../components/PreannotationProfileDialog.vue";
import ConnectionTestResult from "../components/ConnectionTestResult.vue";
const user = useUserStore(),
  profiles = ref([]),
  selected = ref(null),
  dialog = ref(false),
  editing = ref(null),
  loading = ref(true),
  error = ref(false),
  testing = ref(false),
  result = ref(null);
async function load(profile) {
  loading.value = true;
  error.value = false;
  try {
    profiles.value = (await api.get("/preannotation/profiles")).data;
    selected.value =
      profiles.value.find(
        (p) => p.id === (profile?.id || selected.value?.id),
      ) ||
      profiles.value[0] ||
      null;
    result.value = null;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}
function edit(profile = null) {
  editing.value = profile;
  dialog.value = true;
}
async function test() {
  testing.value = true;
  result.value = null;
  const id = selected.value.id;
  try {
    const r = await api.post(`/preannotation/profiles/${id}/test`);
    if (selected.value?.id === id) result.value = r.data;
  } catch (error) {
    await reportError(error);
  } finally {
    testing.value = false;
  }
}
onMounted(() => load());
</script>
<template>
  <div>
    <header class="page-heading">
      <div>
        <h1>推理接口</h1>
        <p>连接视觉模型，统一管理团队的推理配置。</p>
      </div>
      <ui-button type="primary" icon="Plus" @click="edit()">添加接口</ui-button>
    </header>
    <ui-alert v-if="error" type="error" title="接口配置加载失败"
      ><ui-button @click="load()">重新加载</ui-button></ui-alert
    >
    <div v-loading="loading" class="profiles-layout">
      <ui-card class="profiles-list"
        ><div class="section-heading">
          <h2>接口配置</h2>
          <ui-tag>{{ profiles.length }}</ui-tag>
        </div>
        <ui-button
          v-for="profile in profiles"
          :key="profile.id"
          variant="ghost"
          :class="{ active: selected?.id === profile.id }"
          @click="
            selected = profile;
            result = null;
          "
          ><span class="profile-icon"><ui-icon name="Server" /></span
          ><span
            ><strong>{{ profile.name }}</strong
            ><small
              >{{
                profile.interface_type === "openai"
                  ? "OpenAI 兼容"
                  : "HTTP JSON"
              }}
              · {{ profile.is_shared ? "共享" : "个人" }}</small
            ></span
          ><ui-icon name="ArrowRight" /></ui-button></ui-card
      ><ui-card v-if="selected" class="panel-padding"
        ><div class="section-heading">
          <div>
            <h2>{{ selected.name }}</h2>
            <p>{{ selected.model || "未指定模型" }}</p>
          </div>
          <ui-tag :type="selected.environment_key ? 'info' : 'success'">{{
            selected.environment_key ? "环境配置" : "可用配置"
          }}</ui-tag>
        </div>
        <dl class="profile-details">
          <dt>Endpoint</dt>
          <dd>{{ selected.endpoint }}</dd>
          <dt>接口格式</dt>
          <dd>{{ selected.interface_type }}</dd>
          <dt>模型</dt>
          <dd>{{ selected.model || "—" }}</dd>
          <dt>坐标系统</dt>
          <dd>{{ selected.coordinate_system }}</dd>
          <dt>响应提取路径</dt>
          <dd>{{ selected.response_path || "整个响应" }}</dd>
          <dt>凭据</dt>
          <dd>
            {{ selected.has_api_key ? "已保存 API Key" : "未配置 API Key" }}
          </dd>
          <dt>连接超时</dt>
          <dd>{{ selected.timeout_seconds }} 秒</dd>
          <dt>最大尝试次数</dt>
          <dd>{{ selected.max_attempts }}</dd>
        </dl>
        <ConnectionTestResult :result="result" />
        <div class="profile-actions">
          <ui-button :loading="testing" @click="test">测试连接</ui-button
          ><ui-button
            type="primary"
            :disabled="
              selected.environment_key ||
              !(user.isAdmin || selected.owner_id === user.user?.id)
            "
            @click="edit(selected)"
            >编辑配置</ui-button
          >
        </div></ui-card
      ><ui-empty
        v-else
        description="还没有推理接口，添加一个模型服务开始预标注"
      />
    </div>
    <PreannotationProfileDialog
      v-model="dialog"
      :profile="editing"
      @saved="load"
    />
  </div>
</template>
<style scoped>
.profiles-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: var(--space-5);
}
.profiles-list {
  padding: var(--space-5) var(--space-4);
  align-self: start;
}
.profiles-list .section-heading {
  padding: 0 7px;
}
.profiles-list > .ui-button {
  width: 100%;
  justify-content: flex-start;
  padding: var(--space-4) var(--space-3);
  gap: var(--space-3);
  text-align: left;
  margin-bottom: 6px;
}
.profiles-list > .ui-button.active {
  background: #edf1ff;
  color: var(--primary);
}
.profiles-list > .ui-button > span:nth-child(2) {
  flex: 1;
  min-width: 0;
}
.profiles-list strong {
  display: block;
  font-size: 12px;
}
.profiles-list small {
  display: block;
  font-size: 10px;
  color: var(--muted);
  margin-top: 7px;
}
.profiles-list > .ui-button > svg {
  width: 13px;
}
.profile-icon {
  width: 34px;
  height: 34px;
  background: var(--surface-muted);
  border-radius: 7px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}
.profile-details {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: var(--space-5);
  margin: var(--space-6) 0 var(--space-7);
  font-size: 12px;
}
.profile-details dt {
  color: var(--muted);
}
.profile-details dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.profile-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: flex-end;
}
@media (max-width: 1000px) {
  .profiles-layout {
    grid-template-columns: 1fr;
  }
  .profiles-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .profiles-list > .section-heading {
    width: 100%;
  }
  .profiles-list > .ui-button {
    width: auto;
    flex: 1;
    min-width: 180px;
  }
}
@media (max-width: 450px) {
  .profile-details {
    grid-template-columns: 100px 1fr;
    gap: var(--space-4);
  }
}
</style>
