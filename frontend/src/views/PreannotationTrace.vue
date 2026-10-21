<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { message } from "../shared/ui/feedback";
import api from "../utils/api";
import TracePayload from "../components/TracePayload.vue";
import PreannotationThumbnail from "../components/PreannotationThumbnail.vue";
import { createTraceDemo } from "../utils/preannotationTraceDemo";

const route = useRoute(),
  router = useRouter();
const props = defineProps({ context: Object, embedded: Boolean });
const emit = defineEmits(["close"]);
const params = computed(() => props.context || route.params);
const data = ref(null),
  attempts = ref([]),
  selectedId = ref(null),
  loading = ref(true),
  refreshing = ref(false);
const error = ref(false),
  pollingError = ref(false),
  retrying = ref(false),
  olderLoading = ref(false);
const demoScenario = ref("success");
const isDemo = computed(() => route.query.demo === "1");
const selected = computed(() =>
  attempts.value.find((a) => a.id === selectedId.value),
);
const stages = computed(() => selected.value?.trace || {});
const normalized = computed(() => stages.value.normalized?.data);
const provider = computed(() => stages.value.parsed?.data);
const request = computed(() => stages.value.request?.data);
const response = computed(() => stages.value.response?.data);
const responseHeaders = computed(() => stages.value.response_headers?.data);
const active = computed(() =>
  ["queued", "running"].includes(data.value?.task_image.execution_status),
);
const imageSrc = computed(() =>
  isDemo.value
    ? "/preannotation-demo.png"
    : `/api/images/${data.value?.image.id}/file`,
);
const resultImage = computed(() => ({
  ...data.value?.image,
  candidates: (normalized.value?.annotations || []).map((a, i) => ({
    ...a,
    id: i,
  })),
}));
const itemLabel = computed(() =>
  data.value?.task_image.execution_status === "queued" &&
  data.value?.task_image.error_code
    ? "等待自动重试"
    : labels[data.value?.task_image.execution_status] || "等待领取",
);
const labels = {
  queued: "等待领取",
  running: "推理中",
  succeeded: "成功",
  failed: "失败",
  cancelled: "已取消",
  interrupted: "已中断",
};
let generation = 0,
  timer,
  disposed = false,
  requestInFlight = false;
const endpoint = () =>
  `/preannotation/tasks/${params.value.taskId}/images/${params.value.imageId}`;
const context = () =>
  `${params.value.datasetId}:${params.value.taskId}:${params.value.imageId}:${isDemo.value}`;

function apply(result, reset = false) {
  const followLatest =
    reset ||
    !selectedId.value ||
    selectedId.value === attempts.value.at(-1)?.id;
  data.value = result;
  const merged = new Map((reset ? [] : attempts.value).map((a) => [a.id, a]));
  result.attempts.forEach((a) => merged.set(a.id, a));
  attempts.value = [...merged.values()].sort((a, b) => a.id - b.id);
  if (followLatest) selectedId.value = attempts.value.at(-1)?.id || null;
}
async function load(reset = false) {
  if (!reset && requestInFlight) return;
  const token = reset ? ++generation : generation,
    key = context();
  if (reset) {
    loading.value = true;
    error.value = false;
    data.value = null;
    attempts.value = [];
    selectedId.value = null;
  }
  requestInFlight = true;
  refreshing.value = true;
  try {
    const result = isDemo.value
      ? createTraceDemo(
          Number(params.value.datasetId),
          Number(params.value.taskId),
          Number(params.value.imageId),
          demoScenario.value,
        )
      : (await api.get(endpoint() + "/trace")).data;
    if (disposed || token !== generation || key !== context()) return;
    if (result.image.dataset_id !== Number(params.value.datasetId))
      throw new Error("图片不属于当前数据集");
    apply(result, reset);
    pollingError.value = false;
    error.value = false;
  } catch {
    if (token === generation) {
      if (reset) error.value = true;
      else pollingError.value = true;
    }
  } finally {
    if (token === generation) {
      loading.value = false;
      refreshing.value = false;
      requestInFlight = false;
    }
  }
}
async function loadOlder() {
  if (olderLoading.value || !attempts.value.length) return;
  const token = generation,
    url = endpoint();
  olderLoading.value = true;
  try {
    const result = (
      await api.get(url + "/trace", {
        params: { before_id: attempts.value[0].id },
      })
    ).data;
    if (token === generation) {
      const existing = new Map(attempts.value.map((a) => [a.id, a]));
      result.attempts.forEach((a) => existing.set(a.id, a));
      attempts.value = [...existing.values()].sort((a, b) => a.id - b.id);
    }
  } catch {
  } finally {
    if (token === generation) olderLoading.value = false;
  }
}
async function retry() {
  if (!data.value?.can_retry || retrying.value) return;
  const token = generation;
  retrying.value = true;
  try {
    if (isDemo.value) {
      demoScenario.value = "running";
      message.info("示例已切换为推理中，没有提交真实任务");
      return;
    }
    await api.post(endpoint() + "/retry");
    if (token !== generation) return;
    message.success("已重新排队，历史记录已保留");
    await load();
  } catch {
  } finally {
    if (token === generation || isDemo.value) retrying.value = false;
  }
}
function back() {
  if (props.embedded) {
    emit("close");
    return;
  }
  router.push({
    name: "Preannotation",
    params: { datasetId: params.value.datasetId },
    query: {
      task: isDemo.value ? route.query.returnTask : params.value.taskId,
      ...Object.fromEntries(
        Object.entries(route.query).filter(([key]) =>
          [
            "review_status",
            "has_candidates",
            "execution_status",
            "page",
          ].includes(key),
        ),
      ),
    },
  });
}
function reviewImage() {
  router.push({
    name: "Annotation",
    params: { datasetId: params.value.datasetId },
    query: {
      source: "preannotation",
      task: params.value.taskId,
      image: params.value.imageId,
      review_status: "all",
    },
  });
}
function duration(ms) {
  return ms == null
    ? "—"
    : ms >= 60000
      ? `${(ms / 60000).toFixed(1)} 分钟`
      : `${(ms / 1000).toFixed(2)} 秒`;
}
function time(value) {
  return value
    ? new Date(value).toLocaleTimeString("zh-CN", { hour12: false })
    : "";
}
watch(
  context,
  () => {
    requestInFlight = false;
    retrying.value = false;
    olderLoading.value = false;
    load(true);
  },
  { immediate: true },
);
watch(demoScenario, () => {
  if (isDemo.value) load(true);
});
onMounted(() => {
  timer = setInterval(() => {
    if (
      !isDemo.value &&
      active.value &&
      !pollingError.value &&
      !document.hidden
    )
      load();
  }, 4000);
});
onUnmounted(() => {
  disposed = true;
  generation++;
  clearInterval(timer);
});
</script>

<template>
  <div class="trace-page" :class="{ embedded }" v-loading="loading">
    <header class="trace-header">
      <div>
        <ui-button v-if="!embedded" link @click="back"
          >← 返回批次结果</ui-button
        >
        <h1>
          图像推理记录 <span v-if="data">#{{ data.task.id }}</span>
        </h1>
        <p>查看这张图片的输入、服务返回与转换结果。</p>
      </div>
      <div class="header-actions">
        <ui-button :loading="refreshing" @click="load()">刷新记录</ui-button
        ><ui-button
          v-if="data?.can_retry"
          type="warning"
          :loading="retrying"
          @click="retry"
          >重试此图</ui-button
        ><ui-button
          v-if="data?.task_image.execution_status === 'succeeded' && !isDemo"
          type="primary"
          @click="reviewImage"
          >打开审核工作台</ui-button
        >
      </div>
    </header>
    <div v-if="isDemo" class="demo-banner">
      <div>
        <strong>交互示例 · Mock</strong
        ><span>仅演示界面，输入输出为样例，不调用接口或保存数据。</span>
      </div>
      <ui-select v-model="demoScenario" aria-label="示例状态"
        ><ui-option label="成功（含一次失败记录）" value="success" /><ui-option
          label="失败与重试"
          value="failed" /><ui-option
          label="推理进行中"
          value="running" /><ui-option label="旧任务无完整记录" value="legacy"
      /></ui-select>
    </div>
    <ui-alert
      v-if="pollingError"
      title="自动刷新已暂停，已加载记录仍可查看。请点击刷新重试。"
      type="warning"
      :closable="false"
      show-icon
    />
    <ui-empty
      v-if="error"
      description="无法加载推理记录，请检查批次权限与服务状态"
      ><ui-button @click="load(true)">重新加载</ui-button></ui-empty
    >
    <div v-if="data" class="trace-layout">
      <aside class="attempts-rail">
        <div class="rail-heading">
          <h2>请求历史</h2>
          <span>{{ data.total }} 条</span>
        </div>
        <p class="rail-hint">每次重试保留独立记录</p>
        <ui-button
          v-if="attempts.length < data.total && !isDemo"
          class="older-button"
          :loading="olderLoading"
          @click="loadOlder"
          >加载更早记录</ui-button
        >
        <ui-button
          variant="ghost"
          v-for="attempt in [...attempts].reverse()"
          :key="attempt.id"
          class="attempt-link"
          :class="{ selected: selectedId === attempt.id }"
          @click="selectedId = attempt.id"
        >
          <span class="attempt-title"
            >{{
              attempt.trace.legacy
                ? "旧记录"
                : `第 ${attempt.sequence_number} 次`
            }}
            <span class="status-dot" :class="attempt.status"></span
          ></span>
          <span
            >{{ labels[attempt.status] }} ·
            {{ duration(attempt.elapsed_ms) }}</span
          ><small v-if="attempt.error_code">{{ attempt.error_code }}</small>
        </ui-button>
        <div v-if="!attempts.length" class="no-attempt">
          {{
            data.task_image.execution_status === "queued"
              ? "worker 尚未领取图片"
              : "此任务尚无分阶段记录"
          }}
        </div>
      </aside>

      <section class="conversation" aria-label="推理对话记录">
        <div class="conversation-heading">
          <div>
            <strong>{{ data.image.filename }}</strong
            ><span>{{ data.image.width }} × {{ data.image.height }}</span>
          </div>
          <ui-tag
            :type="
              data.task_image.execution_status === 'failed'
                ? 'danger'
                : data.task_image.execution_status === 'succeeded'
                  ? 'success'
                  : 'info'
            "
            >{{ itemLabel }}</ui-tag
          >
        </div>
        <div class="message user-message">
          <div class="avatar user-avatar">你</div>
          <div class="message-content">
            <div class="message-meta">
              用户输入
              <span v-if="stages.request">{{ time(stages.request.at) }}</span>
            </div>
            <div class="user-bubble">
              <p>{{ request?.prompt || data.input.prompt }}</p>
              <span class="image-attachment"
                >图片 · {{ data.image.filename }}</span
              >
            </div>
            <small v-if="!request" class="muted"
              >批次 Prompt 快照；本次实际请求尚未记录。</small
            >
          </div>
        </div>

        <template v-if="selected">
          <ui-alert
            v-if="data.task_image.execution_status === 'queued'"
            class="legacy-notice"
            :title="
              data.task_image.error_code
                ? '等待自动重试；也可以点击重试此图立即重新排队。'
                : '图片已排队，worker 领取后会新增一条记录。'
            "
            type="info"
            :closable="false"
          />
          <ui-alert
            v-if="stages.legacy"
            class="legacy-notice"
            title="这是升级前保留的错误 / 响应快照，实际请求和耗时没有记录。"
            type="info"
            :closable="false"
          />
          <div class="message">
            <div class="avatar service-avatar">↗</div>
            <div class="message-content">
              <div class="message-meta">
                发送到推理接口
                <span>第 {{ selected.sequence_number }} 次请求</span>
              </div>
              <template v-if="request"
                ><div class="endpoint-line">
                  <span>{{ request.method }}</span
                  >{{ request.endpoint }}
                </div>
                <TracePayload
                  title="完整请求体（图片以原图引用展示）"
                  :value="request.body" /><TracePayload
                  title="请求头（认证信息已隐藏）"
                  :value="request.headers" /><TracePayload
                  title="输出 Schema 与转换规则"
                  :value="{
                    schema: request.output_schema,
                    conversion: request.conversion,
                  }"
              /></template>
              <p v-else class="muted">
                请求尚未发出，或在读取图片 / 准备凭据阶段失败。
              </p>
            </div>
          </div>
          <div class="message">
            <div class="avatar assistant-avatar">AI</div>
            <div class="message-content">
              <div class="message-meta">
                模型返回
                <span v-if="responseHeaders"
                  >HTTP {{ responseHeaders.http_status }}</span
                ><span v-if="stages.response">{{
                  time(stages.response.at)
                }}</span>
              </div>
              <div
                v-if="provider?.reasoning_content"
                class="provider-reasoning"
              >
                <ui-collapsible title="服务返回的推理说明">
                  <pre>{{ provider.reasoning_content }}</pre>
                </ui-collapsible>
              </div>
              <TracePayload
                v-if="provider"
                title="模型输出"
                :value="provider.output"
                :expanded="true"
              />
              <div
                v-if="!response && selected.status === 'running'"
                class="waiting-message"
              >
                <ui-icon class="is-loading"><Loading /></ui-icon>
                <div>
                  <strong>正在等待模型响应</strong>
                  <p>不设整图总耗时和读取时限，可返回任务页取消。</p>
                </div>
              </div>
              <p v-else-if="!response" class="muted">
                这次请求没有取得响应正文。
              </p>
              <TracePayload
                v-if="response"
                title="完整原始响应"
                :value="response.raw"
                :expanded="!provider"
              />
              <TracePayload
                v-if="responseHeaders"
                title="响应状态与请求标识"
                :value="responseHeaders"
              />
              <div v-if="provider?.usage" class="usage-line">
                <span v-for="(value, key) in provider.usage" :key="key"
                  >{{ key }}:
                  {{
                    typeof value === "object" ? JSON.stringify(value) : value
                  }}</span
                >
              </div>
            </div>
          </div>
          <div v-if="normalized" class="message">
            <div class="avatar result-avatar">✓</div>
            <div class="message-content">
              <div class="message-meta">平台转换与校验</div>
              <div class="validation-success">
                <strong>校验通过 · {{ normalized.count }} 个候选框</strong>
                <p>
                  已转换为当前标注
                  Schema。候选框需要人工审核后才能进入正式标注。
                </p>
              </div>
              <TracePayload
                title="标准化标注结果"
                :value="normalized.annotations"
              />
            </div>
          </div>
          <div v-if="selected.error_message" class="message">
            <div class="avatar error-avatar">!</div>
            <div class="message-content">
              <div class="message-meta">执行结果</div>
              <div class="failure-message">
                <strong>{{ selected.error_message }}</strong
                ><code>{{ selected.error_code }}</code>
                <p>
                  本次记录已保留。{{
                    data.can_retry
                      ? "可以重试此图，或在任务页批量重试失败图片。"
                      : "可在左侧切换查看其他尝试。"
                  }}
                </p>
              </div>
            </div>
          </div>
          <div class="attempt-footer">
            <span
              >第 {{ selected.sequence_number }} 次 ·
              {{ labels[selected.status] }} ·
              {{ duration(selected.elapsed_ms) }}</span
            ><span v-if="responseHeaders?.request_id">{{
              responseHeaders.request_id
            }}</span>
          </div>
        </template>
        <div v-else class="legacy-state">
          <ui-alert
            :title="
              data.task_image.execution_status === 'queued'
                ? '图片等待领取，执行后会在这里显示每个阶段。'
                : '旧任务未记录完整请求与阶段信息，无法补还原。'
            "
            type="info"
            :closable="false"
            show-icon
          /><TracePayload
            title="批次配置快照"
            :value="data.input"
          /><TracePayload
            v-if="data.legacy_response"
            title="已有原始响应"
            :value="data.legacy_response"
            :expanded="true"
          /><ui-alert
            v-if="data.task_image.error_message"
            :title="data.task_image.error_message"
            type="error"
            :closable="false"
          />
        </div>
      </section>

      <aside class="image-context">
        <h2>{{ normalized ? "候选结果预览" : "输入图片" }}</h2>
        <PreannotationThumbnail
          :image="resultImage"
          :image-url="imageSrc"
          :categories="data.input.categories"
          :overlay="!!normalized"
        /><strong>{{ data.image.filename }}</strong>
        <dl>
          <dt>模型</dt>
          <dd>{{ data.input.model || "接口默认模型" }}</dd>
          <dt>接口</dt>
          <dd>
            {{
              data.input.interface_type === "openai"
                ? "OpenAI 兼容"
                : "HTTP JSON"
            }}
          </dd>
          <dt>批次</dt>
          <dd>#{{ data.task.id }}</dd>
          <dt>类别</dt>
          <dd>{{ data.input.categories.map((c) => c.name).join("、") }}</dd>
          <dt>响应等待</dt>
          <dd>无总耗时限制</dd>
        </dl>
        <TracePayload
          v-if="request?.image"
          title="输入图片元数据"
          :value="request.image"
        />
        <p class="context-note">
          只展示服务实际返回的推理说明。服务未返回时不生成补充内容。
        </p>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.trace-page {
  color: #28394c;
  min-width: 0;
}
.trace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-5);
  margin-bottom: var(--space-5);
}
.trace-header h1 {
  font-size: 25px;
  margin: var(--space-3) 0 6px;
  letter-spacing: -0.5px;
}
.trace-header h1 span {
  color: #93a1b3;
  font-weight: 400;
  font-size: 19px;
  margin-left: var(--space-2);
}
.trace-header p {
  margin: 0;
  color: #78889b;
  font-size: 13px;
}
.header-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.header-actions .ui-button {
  margin: 0;
}
.demo-banner {
  padding: var(--space-4) var(--space-4);
  border: 1px solid #e6d8af;
  background: #fffbef;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  border-radius: 8px;
  margin-bottom: var(--space-5);
}
.demo-banner strong {
  color: #956719;
  font-size: 13px;
}
.demo-banner span {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  color: #8e7957;
}
.demo-banner .ui-select {
  width: 220px;
  flex-shrink: 0;
}
.trace-layout {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr) 250px;
  gap: var(--space-5);
  align-items: start;
}
.attempts-rail {
  position: sticky;
  top: 20px;
}
.rail-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.rail-heading h2,
.image-context h2 {
  font-size: 13px;
  margin: 0;
  font-weight: 600;
}
.rail-heading span,
.rail-hint {
  font-size: 11px;
  color: #8796a6;
}
.rail-hint {
  margin: var(--space-3) 0 var(--space-4);
}
.attempt-link {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  width: 100%;
  text-align: left;
  padding: var(--space-4);
  border: 1px solid transparent;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  color: #8a97a7;
  font-size: 11px;
  margin-bottom: 6px;
}
.attempt-link.selected {
  border-color: #cfdeee;
  background: #eaf2fb;
  color: #50749b;
}
.attempt-title {
  font-size: 13px;
  color: #4b5d72;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.attempt-link.selected .attempt-title {
  color: #2563a7;
  font-weight: 600;
}
.attempt-link small {
  font-family: monospace;
}
.status-dot {
  height: 7px;
  width: 7px;
  border-radius: 50%;
  background: #98a7b8;
}
.status-dot.succeeded {
  background: #29a682;
}
.status-dot.failed {
  background: #dd775e;
}
.status-dot.running {
  background: #409eff;
}
.no-attempt {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.7;
}
.older-button {
  width: 100%;
  margin-bottom: var(--space-3);
}
.conversation {
  min-width: 0;
  background: #fff;
  border: 1px solid #e0e7ef;
  border-radius: 12px;
  overflow: hidden;
}
.conversation-heading {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid #e7ecf3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.conversation-heading strong {
  font-size: 13px;
  overflow-wrap: anywhere;
}
.conversation-heading span:not(.ui-tag) {
  font-size: 11px;
  color: #94a3b8;
  margin-left: var(--space-3);
}
.message {
  display: flex;
  gap: var(--space-3);
  margin: var(--space-5) var(--space-5);
}
.avatar {
  flex: 0 0 28px;
  height: 28px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
}
.user-avatar {
  background: #e9effa;
  color: #627ba9;
}
.service-avatar {
  background: #edf1f6;
  color: #6c7c8e;
  font-size: 16px;
}
.assistant-avatar {
  background: #153f64;
  color: white;
}
.result-avatar {
  background: #e4f4ed;
  color: #24916e;
}
.error-avatar {
  background: #fae9e3;
  color: #cb694d;
}
.message-content {
  min-width: 0;
  flex: 1;
}
.message-meta {
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin: 6px 0 var(--space-3);
}
.message-meta span {
  font-weight: 400;
  font-size: 10px;
  color: #8f9cac;
}
.user-bubble {
  padding: var(--space-4) var(--space-4);
  background: #f0f5fc;
  border: 1px solid #e5edf8;
  border-radius: 0 10px 10px 10px;
}
.user-bubble p {
  margin: 0;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.image-attachment {
  display: inline-block;
  margin-top: var(--space-3);
  font-size: 11px;
  padding: 6px var(--space-2);
  border: 1px solid #d9e5f3;
  border-radius: 5px;
  color: #6081a3;
  background: #fff;
  overflow-wrap: anywhere;
  max-width: 100%;
}
.endpoint-line {
  font-family: monospace;
  font-size: 11px;
  color: #718398;
  overflow-wrap: anywhere;
  line-height: 1.7;
}
.endpoint-line span {
  color: #37927a;
  margin-right: var(--space-2);
}
.muted {
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.7;
  display: block;
  margin-top: var(--space-3);
}
.provider-reasoning {
  background: #f5f6f8;
  padding: var(--space-3);
  border-radius: 8px;
  color: #7b8796;
  font-size: 12px;
}
.provider-reasoning summary {
  cursor: pointer;
}
.provider-reasoning pre {
  font: inherit;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.waiting-message {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-5);
  background: #f5f8fc;
  border-radius: 8px;
  color: #6b86a3;
  font-size: 12px;
}
.waiting-message p {
  margin: var(--space-2) 0 0;
  line-height: 1.6;
}
.validation-success {
  border-left: 3px solid #4eb18f;
  padding: var(--space-3) var(--space-4);
  background: #f1f9f5;
  font-size: 12px;
  color: #43846d;
}
.validation-success p {
  margin: var(--space-2) 0 0;
  font-size: 11px;
  line-height: 1.7;
}
.failure-message {
  background: #fff6f3;
  border: 1px solid #f4ded5;
  border-radius: 8px;
  padding: var(--space-4);
  color: #bc674d;
  font-size: 12px;
}
.failure-message code {
  display: block;
  margin-top: var(--space-3);
  color: #a78372;
}
.failure-message p {
  font-size: 11px;
  margin: var(--space-3) 0 0;
  line-height: 1.8;
}
.usage-line {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-top: var(--space-3);
  font-size: 10px;
  color: #95a1b0;
}
.attempt-footer {
  border-top: 1px solid #edf0f4;
  padding: var(--space-4) var(--space-5);
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  overflow-wrap: anywhere;
  font-size: 10px;
  color: #94a3b8;
}
.legacy-state {
  padding: var(--space-5);
}
.image-context {
  padding: var(--space-4);
  background: #fff;
  border: 1px solid #e0e7ef;
  border-radius: 10px;
  min-width: 0;
}
.image-context h2 {
  margin-bottom: var(--space-4);
}
.image-context .thumbnail {
  border: 1px solid #e6ecf2;
  border-radius: 6px;
}
.image-context > strong {
  font-size: 11px;
  margin-top: var(--space-3);
  display: block;
  overflow-wrap: anywhere;
}
.image-context dl {
  display: grid;
  grid-template-columns: 65px minmax(0, 1fr);
  gap: var(--space-4) var(--space-2);
  font-size: 11px;
  margin: var(--space-5) 0;
}
.image-context dt {
  color: #8d9aaa;
}
.image-context dd {
  margin: 0;
  color: #5f738a;
  overflow-wrap: anywhere;
}
.context-note {
  border-top: 1px solid #edf0f5;
  padding-top: var(--space-4);
  margin: var(--space-4) 0 0;
  color: #96a3b3;
  font-size: 10px;
  line-height: 1.8;
}
@media (max-width: 1250px) {
  .trace-layout {
    grid-template-columns: 145px minmax(0, 1fr);
  }
  .image-context {
    grid-column: 2;
    display: block;
  }
  .image-context .thumbnail {
    max-width: 280px;
  }
  .trace-header {
    align-items: flex-start;
  }
  .message {
    margin: var(--space-5) var(--space-4);
  }
  .conversation-heading {
    padding: var(--space-4);
  }
}
@media (max-width: 700px) {
  .trace-header {
    flex-direction: column;
  }
  .trace-layout {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-4);
  }
  .attempts-rail {
    position: static;
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .rail-heading {
    width: 100%;
  }
  .rail-hint {
    width: 100%;
    margin: 0;
  }
  .attempt-link {
    width: auto;
    min-width: 120px;
    padding: var(--space-3);
  }
  .image-context {
    grid-column: 1;
  }
  .demo-banner {
    flex-direction: column;
    align-items: stretch;
  }
  .demo-banner .ui-select {
    width: 100%;
  }
  .message {
    margin: var(--space-4) var(--space-3);
    gap: var(--space-2);
  }
  .avatar {
    flex-basis: 24px;
    height: 24px;
  }
  .conversation-heading {
    padding: var(--space-4);
  }
  .conversation-heading > div span {
    display: block;
    margin: 6px 0 0;
  }
  .attempt-footer {
    padding: var(--space-4);
  }
  .image-context .thumbnail {
    max-width: 100%;
  }
  .trace-header h1 {
    font-size: 22px;
  }
}
</style>
