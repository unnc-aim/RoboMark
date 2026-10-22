<script setup>
import { ref, watch, computed, nextTick } from "vue";
import { message, messageBox } from "../shared/ui/feedback";
import { useUserStore } from "../stores/user";
import api, { reportError } from "../utils/api";
import ConnectionTestResult from "./ConnectionTestResult.vue";

const props = defineProps({ modelValue: Boolean, profile: Object });
const emit = defineEmits(["update:modelValue", "saved"]);
const user = useUserStore();
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});
const form = ref({});
const busy = ref(false);
const testing = ref(false),
  testResult = ref(null);
const connectionFeedback = ref(null);
let testGeneration = 0;
const templateText = ref("");
const headersText = ref("{}");
const mappingText = ref("{}");
const defaultTemplate = {
  image: "{{image.data_url}}",
  prompt: "{{prompt}}",
  model: "{{model}}",
  schema: "{{output_schema}}",
};

watch(
  () => props.modelValue,
  (value) => {
    testGeneration++;
    testing.value = false;
    testResult.value = null;
    if (!value) return;
    form.value = {
      name: "",
      endpoint: "",
      interface_type: "openai",
      http_method: "POST",
      model: "",
      api_key: "",
      clear_credentials: false,
      response_path: "choices[0].message.content",
      annotations_path: "annotations",
      coordinate_system: "normalized",
      box_format: "center",
      structured_output: "none",
      timeout_seconds: 120,
      max_attempts: 3,
      is_shared: false,
      ...props.profile,
    };
    form.value.api_key = "";
    templateText.value = JSON.stringify(
      props.profile?.request_template || defaultTemplate,
      null,
      2,
    );
    headersText.value = JSON.stringify(props.profile?.headers || {}, null, 2);
    mappingText.value = JSON.stringify(
      props.profile?.field_mapping || {},
      null,
      2,
    );
  },
  { immediate: true },
);

function changeInterface(value) {
  form.value.response_path =
    value === "openai" ? "choices[0].message.content" : "";
}

watch(
  [form, templateText, headersText, mappingText],
  () => {
    testResult.value = null;
  },
  { deep: true },
);

function payloadForRequest(test = false) {
  let payload;
  payload = Object.fromEntries(
    [
      "name",
      "endpoint",
      "interface_type",
      "http_method",
      "model",
      "response_path",
      "annotations_path",
      "coordinate_system",
      "box_format",
      "structured_output",
      "timeout_seconds",
      "max_attempts",
      "is_shared",
      "clear_credentials",
    ].map((k) => [k, form.value[k]]),
  );
  payload.api_key = form.value.api_key || null;
  payload.headers = JSON.parse(headersText.value);
  payload.field_mapping = JSON.parse(mappingText.value);
  payload.request_template =
    form.value.interface_type === "http_json"
      ? JSON.parse(templateText.value)
      : {};
  if (test && !payload.name.trim()) payload.name = "连接测试";
  return payload;
}

async function testConnection() {
  if (!form.value.endpoint.trim()) return message.warning("请先填写 endpoint");
  let payload;
  try {
    payload = payloadForRequest(true);
  } catch {
    return message.error("请求头、字段映射和请求模板必须是有效 JSON");
  }
  const generation = ++testGeneration;
  testing.value = true;
  testResult.value = null;
  try {
    const response = await api.post("/preannotation/profiles/test", {
      profile: payload,
      existing_profile_id: props.profile?.id || null,
    });
    if (generation === testGeneration) {
      testResult.value = response.data;
      await nextTick();
      if (generation === testGeneration && visible.value)
        connectionFeedback.value?.$el?.scrollIntoView?.({ block: "nearest" });
    }
  } catch {
    /* 错误统一由拦截器提示 */
  } finally {
    if (generation === testGeneration) testing.value = false;
  }
}

async function save() {
  if (!form.value.name.trim() || !form.value.endpoint.trim())
    return message.warning("请填写名称和 endpoint");
  let payload;
  try {
    payload = payloadForRequest();
  } catch {
    return message.error("请求头、字段映射和请求模板必须是有效 JSON");
  }
  busy.value = true;
  try {
    const response = props.profile
      ? await api.put(`/preannotation/profiles/${props.profile.id}`, payload)
      : await api.post("/preannotation/profiles", payload);
    message.success("接口配置已保存");
    emit("saved", response.data);
    visible.value = false;
  } catch (error) {
    await reportError(error);
  } finally {
    busy.value = false;
  }
}

async function remove() {
  try {
    await messageBox.confirm(
      "停用后，未完成任务将无法使用此配置继续推理。",
      "停用接口配置",
      { type: "warning" },
    );
  } catch {
    return;
  }
  busy.value = true;
  try {
    await api.delete(`/preannotation/profiles/${props.profile.id}`);
    emit("saved", null);
    visible.value = false;
  } catch (error) {
    await reportError(error);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <ui-dialog
    v-model="visible"
    class="connection-profile-dialog"
    top="5vh"
    :title="profile ? '编辑推理接口' : '添加推理接口'"
    width="min(720px, 94vw)"
    :close-on-click-modal="false"
  >
    <ui-form
      label-position="top"
      class="profile-form"
      :disabled="busy || testing"
      @submit.prevent="save"
    >
      <div class="two-cols">
        <ui-form-item label="配置名称"
          ><ui-input v-model="form.name" placeholder="例如：局域网 vLLM"
        /></ui-form-item>
        <ui-form-item label="接口格式"
          ><ui-select v-model="form.interface_type" @change="changeInterface"
            ><ui-option label="OpenAI 兼容" value="openai" /><ui-option
              label="自定义 HTTP JSON"
              value="http_json" /></ui-select
        ></ui-form-item>
      </div>
      <ui-form-item label="Endpoint（完整请求地址）"
        ><ui-input
          v-model="form.endpoint"
          placeholder="http://server:8000/v1/chat/completions"
      /></ui-form-item>
      <div class="two-cols">
        <ui-form-item label="模型名"
          ><ui-input v-model="form.model" placeholder="服务中的 model 名称"
        /></ui-form-item>
        <ui-form-item
          :label="
            profile?.has_api_key
              ? 'API Key（已保存，留空保留）'
              : 'API Key（可选）'
          "
          ><ui-input
            v-model="form.api_key"
            type="password"
            show-password
            autocomplete="new-password"
        /></ui-form-item>
      </div>
      <ui-form-item label="请求头 JSON"
        ><ui-input v-model="headersText" type="textarea" :rows="3" /><small
          >已有值显示为 [已保存]；保留该值可保留原请求头。</small
        ></ui-form-item
      >
      <ui-checkbox v-model="form.clear_credentials"
        >清除已保存的 API Key 和请求头</ui-checkbox
      >
      <template v-if="form.interface_type === 'http_json'">
        <ui-form-item label="HTTP 方法"
          ><ui-select v-model="form.http_method"
            ><ui-option value="POST" /><ui-option value="PUT" /></ui-select
        ></ui-form-item>
        <ui-form-item label="请求模板 JSON"
          ><ui-input v-model="templateText" type="textarea" :rows="7" /><small
            v-pre
            >占位符：{{ image.data_url }}、{{ prompt }}、{{ user_prompt }}、{{
              categories
            }}、{{ output_schema }}、{{
              model
            }}。完整占位符保留对象或数组类型。</small
          ></ui-form-item
        >
      </template>
      <div class="two-cols">
        <ui-form-item label="响应提取路径"
          ><ui-input
            v-model="form.response_path"
            placeholder="留空使用整个响应"
        /></ui-form-item>
        <ui-form-item label="候选数组路径"
          ><ui-input
            v-model="form.annotations_path"
            placeholder="annotations；顶层数组可留空"
        /></ui-form-item>
        <ui-form-item label="模型输出坐标"
          ><ui-select v-model="form.coordinate_system"
            ><ui-option label="归一化 0–1" value="normalized" /><ui-option
              label="原图像素"
              value="pixels" /><ui-option
              label="相对坐标 0–1000"
              value="relative_1000" /></ui-select
        ></ui-form-item>
        <ui-form-item label="矩形输出格式"
          ><ui-select v-model="form.box_format"
            ><ui-option label="中心点 + 宽高" value="center" /><ui-option
              label="bbox: [x1, y1, x2, y2]"
              value="xyxy" /></ui-select
        ></ui-form-item>
      </div>
      <ui-form-item label="字段映射 JSON"
        ><ui-input
          v-model="mappingText"
          type="textarea"
          :rows="3"
          placeholder='例如：{"bbox":"bbox_2d","label":"label"}'
        /><small
          >键为平台字段，值为模型输出中每个对象的字段路径；可用类别名称 label
          映射类别。</small
        ></ui-form-item
      >
      <ui-form-item v-if="form.interface_type === 'openai'" label="结构化输出"
        ><ui-select v-model="form.structured_output"
          ><ui-option label="Prompt 约束" value="none" /><ui-option
            label="response_format / JSON Schema"
            value="response_format" /><ui-option
            label="vLLM structured_outputs"
            value="vllm" /></ui-select
      ></ui-form-item>
      <div class="two-cols">
        <ui-form-item label="连接 / 发送超时（秒）"
          ><ui-input-number
            v-model="form.timeout_seconds"
            :min="5"
            :max="600"
          /><small
            >不限制模型响应的总耗时与读取等待，可在任务页手动取消。</small
          ></ui-form-item
        >
        <ui-form-item label="最大尝试次数"
          ><ui-input-number v-model="form.max_attempts" :min="1" :max="5"
        /></ui-form-item>
      </div>
      <ui-checkbox v-if="user.isAdmin" v-model="form.is_shared"
        >共享给其他用户</ui-checkbox
      >
    </ui-form>
    <ConnectionTestResult ref="connectionFeedback" :result="testResult" />
    <template #footer>
      <ui-button
        v-if="profile"
        type="danger"
        plain
        :disabled="busy || testing"
        @click="remove"
        >停用配置</ui-button
      >
      <ui-button :loading="testing" :disabled="busy" @click="testConnection"
        >测试连接</ui-button
      >
      <ui-button @click="visible = false">取消</ui-button
      ><ui-button
        type="primary"
        :loading="busy"
        :disabled="testing"
        @click="save"
        >保存配置</ui-button
      >
    </template>
  </ui-dialog>
</template>

<style scoped>
:global(.connection-profile-dialog) {
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}
:global(.connection-profile-dialog .ui-dialog__body) {
  min-height: 0;
  overflow-y: auto;
  flex: 1;
}
:global(.connection-profile-dialog .ui-dialog__header),
:global(.connection-profile-dialog .ui-dialog__footer) {
  flex-shrink: 0;
}
.two-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 var(--space-5);
}
.profile-form :deep(.ui-select) {
  width: 100%;
}
.profile-form small {
  display: block;
  color: #6b7280;
  line-height: 1.7;
  margin-top: 6px;
}
.profile-form :deep(textarea) {
  font-family: monospace;
}
.profile-form > .ui-checkbox {
  margin-bottom: var(--space-4);
}
@media (max-width: 600px) {
  .two-cols {
    grid-template-columns: 1fr;
  }
}
</style>
