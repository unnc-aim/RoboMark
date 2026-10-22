<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import { message, messageBox } from "../shared/ui/feedback";
import { useUserStore } from "../stores/user";
import api, { reportError } from "../utils/api";
import PreannotationProfileDialog from "../components/PreannotationProfileDialog.vue";
import PreannotationThumbnail from "../components/PreannotationThumbnail.vue";
import ConnectionTestResult from "../components/ConnectionTestResult.vue";
import PreannotationPromptHistory from "../components/PreannotationPromptHistory.vue";
import DatasetHeader from "../components/DatasetHeader.vue";
import PreannotationTrace from "./PreannotationTrace.vue";

const route = useRoute(),
  router = useRouter(),
  user = useUserStore();
const datasetId = Number(route.params.datasetId);
const traceOpen = ref(false),
  traceContext = ref(null),
  pageSize = ref(6);
const dataset = ref(null),
  profiles = ref([]),
  categories = ref([]),
  tasks = ref([]),
  images = ref([]);
const retryingImages = ref(new Set()),
  busyTasks = ref(new Set());
const loading = ref(true),
  creating = ref(false),
  imageLoading = ref(false),
  imageFailed = ref(false),
  polling = ref(true);
const profileDialog = ref(false),
  editingProfile = ref(null);
const profileId = ref(null),
  prompt = ref(""),
  categoryIds = ref([]),
  shape = ref("bbox"),
  sampleSize = ref(3);
const promptInput = ref(null),
  promptHistoryOpen = ref(false),
  promptFillUndo = ref(null);
const canUndoPromptFill = computed(
  () => promptFillUndo.value && prompt.value === promptFillUndo.value.after,
);
const testingConnection = ref(false),
  connectionResult = ref(null);
const selectedTaskId = ref(Number(route.query.task) || null),
  taskTotal = ref(0),
  taskPage = ref(1);
const page = ref(Math.max(1, Number(route.query.page) || 1)),
  total = ref(0),
  overlay = ref(true);
const filters = ref({
  has_candidates: route.query.has_candidates || "",
  execution_status: route.query.execution_status || "",
  review_status: route.query.review_status || "",
});
const selectedTask = computed(() =>
  tasks.value.find((t) => t.id === selectedTaskId.value),
);
const selectedProfile = computed(() =>
  profiles.value.find((p) => p.id === profileId.value),
);
const canEditProfile = computed(
  () =>
    selectedProfile.value &&
    !selectedProfile.value.environment_key &&
    (user.isAdmin || selectedProfile.value.owner_id === user.user?.id),
);
const taskLabels = {
  queued: "排队中",
  running: "执行中",
  cancelling: "取消中",
  cancelled: "已取消",
  completed: "已完成",
  completed_with_errors: "部分失败",
  failed: "失败",
};
const executionLabels = {
  queued: "未处理",
  running: "处理中",
  succeeded: "成功",
  failed: "失败",
  cancelled: "已取消",
};
const reviewLabels = {
  pending: "待审核（含草稿）",
  unreviewed: "待审核",
  draft: "审核草稿",
  approved: "已通过",
  rejected: "已驳回",
};
const tokenFormatter = new Intl.NumberFormat("zh-CN");
const tokenNumber = (value) =>
  value == null ? "—" : tokenFormatter.format(value);
const tpsNumber = (value) => (value == null ? "—" : Number(value).toFixed(1));
function metricsTooltip(image) {
  const metrics = image.inference_metrics || {};
  const lines = [
    "输入 / 输出 Token 来自服务 usage；仅本次成功尝试，不累计失败重试。",
    metrics.duration_source === "trace"
      ? "TPS = 输出 Token ÷ 记录的请求阶段耗时（估算，包含排队与首 Token 等待），不是纯解码速度。"
      : "TPS = 输出 Token ÷ HTTP 请求耗时（包含排队与首 Token 等待），不是纯解码速度。",
  ];
  if (metrics.input_tokens == null || metrics.output_tokens == null)
    lines.push("服务未返回完整用量，缺项显示 —。");
  if (metrics.elapsed_ms == null) lines.push("没有记录耗时，TPS 显示 —。");
  return lines.join("\n");
}
let timer,
  imageRequest = 0,
  refreshing = false;

function focusPrompt() {
  nextTick(() => {
    promptInput.value?.$el.scrollIntoView({
      block: "center",
      behavior: "smooth",
    });
    promptInput.value?.focus();
  });
}
function fillPrompt(text) {
  if (creating.value || !text?.trim()) return;
  if (text === prompt.value) {
    if (!promptHistoryOpen.value) focusPrompt();
    return;
  }
  promptFillUndo.value = { before: prompt.value, after: text };
  prompt.value = text;
  if (!promptHistoryOpen.value) focusPrompt();
}
function undoPromptFill() {
  if (!canUndoPromptFill.value || creating.value) return;
  prompt.value = promptFillUndo.value.before;
  promptFillUndo.value = null;
  focusPrompt();
}

function imageParams() {
  const params = { page: page.value, page_size: pageSize.value };
  if (selectedTaskId.value) {
    params.task_id = selectedTaskId.value;
    for (const [key, value] of Object.entries(filters.value))
      if (value !== "") params[key] = value;
  }
  return params;
}

async function loadImages(quiet = false) {
  const request = ++imageRequest;
  if (!quiet) imageLoading.value = true;
  imageFailed.value = false;
  try {
    const response = await api.get(`/datasets/${datasetId}/images`, {
      params: imageParams(),
    });
    if (request !== imageRequest) return;
    images.value = response.data.items;
    total.value = response.data.total;
  } catch {
    if (request === imageRequest) imageFailed.value = true;
  } finally {
    if (request === imageRequest) imageLoading.value = false;
  }
}

async function loadTasks() {
  const response = await api.get(`/datasets/${datasetId}/preannotation-tasks`, {
    params: { page: taskPage.value },
  });
  tasks.value = response.data.items;
  taskTotal.value = response.data.total;
  if (
    selectedTaskId.value &&
    !tasks.value.some((t) => t.id === selectedTaskId.value)
  ) {
    const selected = await api.get(
      `/preannotation/tasks/${selectedTaskId.value}`,
    );
    tasks.value = [selected.data, ...tasks.value];
  }
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    await loadTasks();
    await loadImages(true);
    polling.value = true;
  } catch {
    polling.value = false;
  } finally {
    refreshing = false;
  }
}

function restoreTaskConfig(id) {
  const task = tasks.value.find((t) => t.id === id);
  if (task) {
    prompt.value = task.prompt;
    profileId.value = task.profile_id || profileId.value;
    shape.value = task.annotation_type || "bbox";
    categoryIds.value = (task.categories_snapshot || [])
      .map((c) => c.id)
      .filter((id) => categories.value.some((c) => c.id === id));
  }
}

async function chooseTask(id) {
  selectedTaskId.value = id;
  restoreTaskConfig(id);
  page.value = 1;
  filters.value = {
    has_candidates: "",
    execution_status: "",
    review_status: "",
  };
  await router.replace({ query: id ? { task: id } : {} });
  await loadImages();
}

async function filterChanged() {
  page.value = 1;
  await loadImages();
}

function configure(profile = null) {
  editingProfile.value = profile;
  profileDialog.value = true;
}

watch(profileId, () => {
  connectionResult.value = null;
});
async function testConnection() {
  if (!profileId.value || testingConnection.value) return;
  const id = profileId.value;
  connectionResult.value = null;
  testingConnection.value = true;
  try {
    const response = await api.post(`/preannotation/profiles/${id}/test`);
    if (id === profileId.value) connectionResult.value = response.data;
  } catch {
    /* 错误统一由拦截器提示 */
  } finally {
    testingConnection.value = false;
  }
}

async function profileSaved(profile) {
  connectionResult.value = null;
  profiles.value = (await api.get("/preannotation/profiles")).data;
  profileId.value = profile?.id || profiles.value[0]?.id || null;
}

async function createTask(sample) {
  if (sample && (!Number.isInteger(sampleSize.value) || sampleSize.value < 1))
    return message.warning("请输入正整数抽样数量");
  if (!profileId.value || !prompt.value.trim() || !categoryIds.value.length)
    return message.warning("请选择接口、目标类别并填写 Prompt");
  creating.value = true;
  try {
    const body = {
      profile_id: profileId.value,
      prompt: prompt.value.trim(),
      annotation_type: shape.value,
      category_ids: categoryIds.value,
    };
    if (sample) body.sample_size = sampleSize.value;
    const response = await api.post(
      `/datasets/${datasetId}/preannotation-tasks`,
      body,
    );
    taskPage.value = 1;
    await loadTasks();
    await chooseTask(response.data.id);
    polling.value = true;
    message.success(
      sample
        ? "抽样任务已提交，可查看叠加效果"
        : "全量后台任务已提交，关闭页面后继续执行",
    );
  } catch (error) {
    await reportError(error);
  } finally {
    creating.value = false;
  }
}

async function taskAction(task, action) {
  if (action === "cancel") {
    try {
      await messageBox.confirm(
        "取消剩余处理，已生成的结果仍可审核。",
        "取消预标注任务",
        { type: "warning" },
      );
    } catch {
      return;
    }
  }
  if (busyTasks.value.has(task.id)) return;
  busyTasks.value.add(task.id);
  try {
    const result = await api.post(`/preannotation/tasks/${task.id}/${action}`);
    if (action === "retry-failed")
      message.success(
        `已重新排队 ${result.data.retried_images} 张图片，历史记录已保留`,
      );
    await refresh();
  } catch {
  } finally {
    busyTasks.value.delete(task.id);
  }
}

function startReview(task) {
  router.push({
    name: "Annotation",
    params: { datasetId },
    query: { source: "preannotation", task: task.id, review_status: "pending" },
  });
}

function canRetryImage(image) {
  return (
    selectedTask.value &&
    (user.isAdmin || selectedTask.value.created_by === user.user?.id) &&
    !["cancelled", "cancelling"].includes(selectedTask.value.status) &&
    image.review_status === "unreviewed" &&
    (image.execution_status === "failed" ||
      (image.execution_status === "queued" && image.error_code))
  );
}
function openTrace(image) {
  if (!selectedTaskId.value || !image) return;
  traceContext.value = {
    datasetId,
    taskId: selectedTaskId.value,
    imageId: image.id,
  };
  traceOpen.value = true;
}
async function retryImage(image) {
  if (!canRetryImage(image) || retryingImages.value.has(image.id)) return;
  retryingImages.value.add(image.id);
  try {
    await api.post(
      `/preannotation/tasks/${selectedTaskId.value}/images/${image.id}/retry`,
    );
    message.success("已重新排队，历史记录已保留");
    await refresh();
  } catch {
  } finally {
    retryingImages.value.delete(image.id);
  }
}
function openImage(image) {
  if (!selectedTaskId.value)
    return router.push({
      name: "Annotation",
      params: { datasetId },
      query: { source: "manual", image: image.id },
    });
  if (image.execution_status !== "succeeded") return openTrace(image);
  const query = Object.fromEntries(
    Object.entries(filters.value).filter(([, value]) => value !== ""),
  );
  router.push({
    name: "Annotation",
    params: { datasetId },
    query: {
      ...query,
      source: "preannotation",
      task: selectedTaskId.value,
      image: image.id,
      review_status: filters.value.review_status || "all",
      returnPage: page.value,
    },
  });
}

onMounted(async () => {
  try {
    const [d, p, c] = await Promise.all([
      api.get(`/datasets/${datasetId}`),
      api.get("/preannotation/profiles"),
      api.get(`/categories/dataset/${datasetId}`),
    ]);
    dataset.value = d.data;
    profiles.value = p.data;
    categories.value = c.data;
    profileId.value = profiles.value[0]?.id || null;
    categoryIds.value = categories.value.map((c) => c.id);
    await loadTasks();
    restoreTaskConfig(selectedTaskId.value);
    await loadImages();
    timer = setInterval(() => {
      if (
        polling.value &&
        !document.hidden &&
        tasks.value.some((t) =>
          ["queued", "running", "cancelling"].includes(t.status),
        )
      )
        refresh();
    }, 4000);
  } catch {
    polling.value = false;
  } finally {
    loading.value = false;
  }
});
onUnmounted(() => {
  clearInterval(timer);
  imageRequest++;
});
</script>

<template>
  <div class="preannotation-page" v-loading="loading">
    <DatasetHeader
      :dataset-id="datasetId"
      :dataset="dataset"
      :loading="loading"
    />
    <ui-alert
      v-if="!polling"
      title="自动刷新已暂停，请检查服务后点击刷新。"
      type="warning"
      :closable="false"
      show-icon
    />
    <div class="preannotation-layout">
      <aside class="generation-rail">
        <section class="generation-panel">
          <div class="section-title">
            <h2>创建预标注任务</h2>
            <ui-button
              variant="ghost"
              circle
              icon="Server"
              aria-label="管理推理接口"
              title="管理推理接口"
              @click="router.push('/profiles')"
            />
          </div>
          <ui-form label-position="top" @submit.prevent>
            <div class="config-grid">
              <ui-form-item label="推理接口"
                ><div class="interface-picker">
                  <ui-select v-model="profileId" placeholder="选择接口配置"
                    ><ui-option
                      v-for="p in profiles"
                      :key="p.id"
                      :value="p.id"
                      :label="`${p.name}${p.is_shared ? '（共享）' : ''}`" /></ui-select
                  ><ui-button
                    class="interface-action"
                    icon="Plus"
                    circle
                    aria-label="添加接口"
                    title="添加接口"
                    @click="configure()"
                  /><ui-button
                    class="interface-action"
                    icon="Pencil"
                    circle
                    aria-label="编辑接口"
                    title="编辑接口"
                    :disabled="!canEditProfile"
                    @click="configure(selectedProfile)"
                  /><ui-button
                    class="interface-action"
                    icon="FlaskConical"
                    circle
                    aria-label="测试连接"
                    title="测试连接"
                    :disabled="!profileId"
                    :loading="testingConnection"
                    @click="testConnection"
                  /></div
              ></ui-form-item>
              <ui-form-item label="输出形状"
                ><ui-select v-model="shape"
                  ><ui-option value="bbox" label="矩形框" /><ui-option
                    value="parallelogram"
                    label="四点框" /></ui-select
              ></ui-form-item>
              <ui-form-item label="目标类别"
                ><ui-select
                  v-model="categoryIds"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="选择当前数据集的类别"
                  ><ui-option
                    v-for="c in categories"
                    :key="c.id"
                    :value="c.id"
                    :label="c.name" /></ui-select
              ></ui-form-item>
            </div>
            <ConnectionTestResult :result="connectionResult" />
            <ui-alert
              v-if="!categories.length"
              title="该数据集尚无类别，请先配置类别。"
              type="warning"
              :closable="false"
              ><ui-button
                v-if="user.isAdmin"
                link
                @click="router.push(`/admin/categories/${datasetId}`)"
                >配置类别</ui-button
              ></ui-alert
            >
            <ui-form-item label="Prompt" class="prompt-form-item">
              <template #label
                ><div class="prompt-label">
                  <span>Prompt</span
                  ><ui-button
                    link
                    type="primary"
                    :disabled="creating"
                    @click="promptHistoryOpen = true"
                    >历史 Prompt</ui-button
                  >
                </div></template
              >
              <ui-input
                ref="promptInput"
                v-model="prompt"
                aria-label="Prompt"
                :disabled="creating"
                type="textarea"
                :rows="3"
                :maxlength="12000"
                placeholder="例如：标注图片中的所有无人机，框住完整机身；忽略鸟类和远处无法辨认的物体。"
              />
              <div v-if="canUndoPromptFill" class="prompt-fill-feedback">
                <span>已填入历史 Prompt，可继续编辑</span
                ><ui-button
                  link
                  type="primary"
                  :disabled="creating"
                  @click="undoPromptFill"
                  >撤销填充</ui-button
                >
              </div>
            </ui-form-item>
            <div class="generation-actions">
              <span>抽样图片</span
              ><ui-input-number
                v-model="sampleSize"
                aria-label="抽样数量"
                :min="1"
                :max="Math.max(1, dataset?.total_images || 1000000)"
                size="small"
              /><ui-button :loading="creating" @click="createTask(true)"
                >抽样验证</ui-button
              ><ui-button
                type="primary"
                :loading="creating"
                @click="createTask(false)"
                >对整个数据集运行</ui-button
              ><small>已有人工标注保留；每次运行产生一个新批次。</small>
            </div>
          </ui-form>
        </section>
      </aside>
      <div class="preannotation-results">
        <section class="tasks-panel">
          <div class="section-title">
            <h2>任务批次</h2>
            <ui-button size="small" @click="refresh">刷新</ui-button>
          </div>
          <ui-empty
            v-if="!tasks.length"
            description="尚未创建任务，先试运行几张图片"
            :image-size="65"
          />
          <ui-table
            v-else
            :data="tasks"
            size="small"
            @row-click="(task) => chooseTask(task.id)"
          >
            <ui-table-column label="批次" width="115"
              ><template #default="{ row }"
                ><ui-tag :type="selectedTaskId === row.id ? 'primary' : 'info'"
                  >#{{ row.id }} {{ row.is_sample ? "抽样" : "全量" }}</ui-tag
                ></template
              ></ui-table-column
            >
            <ui-table-column prop="prompt" label="Prompt" min-width="200"
              ><template #default="{ row }"
                ><div class="batch-prompt-cell">
                  <span :title="row.prompt">{{ row.prompt }}</span
                  ><ui-button
                    link
                    type="primary"
                    size="small"
                    :disabled="creating"
                    :aria-label="`复用批次 #${row.id} 的 Prompt`"
                    @click.stop="fillPrompt(row.prompt)"
                    >复用</ui-button
                  >
                </div></template
              ></ui-table-column
            >
            <ui-table-column label="进度" min-width="155"
              ><template #default="{ row }"
                ><ui-progress
                  :percentage="
                    Math.round((row.processed_images / row.total_images) * 100)
                  "
                  :stroke-width="5"
                /><small
                  >{{ row.processed_images }} / {{ row.total_images }} 张</small
                ></template
              ></ui-table-column
            >
            <ui-table-column label="状态" width="115"
              ><template #default="{ row }">{{
                taskLabels[row.status]
              }}</template></ui-table-column
            >
            <ui-table-column label="结果 / 空 / 失败" width="145"
              ><template #default="{ row }"
                >{{ row.with_results }} / {{ row.empty_results }} /
                {{ row.counts.failed || 0 }}</template
              ></ui-table-column
            >
            <ui-table-column label="操作" width="250"
              ><template #default="{ row }"
                ><ui-button link type="primary" @click.stop="chooseTask(row.id)"
                  >查看结果</ui-button
                ><ui-button
                  v-if="row.counts.succeeded"
                  link
                  type="primary"
                  @click.stop="startReview(row)"
                  >工作台审核</ui-button
                ><ui-button
                  v-if="
                    (user.isAdmin || row.created_by === user.user?.id) &&
                    ['queued', 'running'].includes(row.status)
                  "
                  link
                  type="danger"
                  @click.stop="taskAction(row, 'cancel')"
                  >取消</ui-button
                ><ui-button
                  v-if="
                    (user.isAdmin || row.created_by === user.user?.id) &&
                    row.retryable_images &&
                    !['cancelled', 'cancelling'].includes(row.status)
                  "
                  link
                  :loading="busyTasks.has(row.id)"
                  @click.stop="taskAction(row, 'retry-failed')"
                  >重试失败</ui-button
                ></template
              ></ui-table-column
            >
          </ui-table>
          <ui-pagination
            v-if="taskTotal > 20"
            v-model:current-page="taskPage"
            :total="taskTotal"
            :page-size="20"
            layout="prev,pager,next"
            @current-change="loadTasks"
          />
        </section>
        <section class="images-panel" v-loading="imageLoading">
          <ui-alert
            v-if="imageFailed"
            type="error"
            title="图片列表加载失败，已保留当前结果"
            ><ui-button size="small" @click="loadImages()"
              >重新加载</ui-button
            ></ui-alert
          >
          <div class="section-title">
            <h2>
              {{
                selectedTask
                  ? `批次 #${selectedTask.id} · 图片与审核`
                  : "数据集图片"
              }}
            </h2>
            <div class="results-display">
              <ui-select
                v-model="pageSize"
                aria-label="每页图片数量"
                style="width: 110px"
                @change="filterChanged"
                ><ui-option :value="6" label="每页 6 张" /><ui-option
                  :value="12"
                  label="每页 12 张" /></ui-select
              ><ui-switch v-model="overlay" active-text="候选框" />
            </div>
          </div>
          <div class="filters">
            <ui-select
              :model-value="selectedTaskId"
              clearable
              aria-label="选择任务批次"
              placeholder="选择任务批次"
              @change="chooseTask"
              ><ui-option
                v-for="t in tasks"
                :key="t.id"
                :value="t.id"
                :label="`#${t.id} ${t.is_sample ? '抽样' : '全量'} · ${t.prompt}`" /></ui-select
            ><ui-select
              v-model="filters.has_candidates"
              placeholder="所有候选结果"
              :disabled="!selectedTaskId"
              @change="filterChanged"
              ><ui-option label="所有候选结果" value="" /><ui-option
                label="存在候选框"
                value="true" /><ui-option
                label="无候选框"
                value="false" /></ui-select
            ><ui-select
              v-model="filters.execution_status"
              placeholder="所有执行状态"
              :disabled="!selectedTaskId"
              @change="filterChanged"
              ><ui-option label="所有执行状态" value="" /><ui-option
                v-for="(label, value) in executionLabels"
                :key="value"
                :label="label"
                :value="value" /></ui-select
            ><ui-select
              v-model="filters.review_status"
              placeholder="所有审核状态"
              :disabled="!selectedTaskId"
              @change="filterChanged"
              ><ui-option label="所有审核状态" value="" /><ui-option
                v-for="(label, value) in reviewLabels"
                :key="value"
                :label="label"
                :value="value" /></ui-select
            ><span>{{ total }} 张</span>
          </div>
          <ui-empty v-if="!images.length" description="没有符合条件的图片" />
          <div class="image-grid">
            <article
              v-for="image in images"
              :key="image.id"
              class="image-card-wrap"
            >
              <ui-button
                variant="ghost"
                class="image-card"
                @click="openImage(image)"
              >
                <PreannotationThumbnail
                  :image="image"
                  :categories="categories"
                  :overlay="overlay"
                />
                <div class="image-card-body">
                  <strong :title="image.filename">{{ image.filename }}</strong>
                  <div v-if="image.execution_status">
                    <ui-tag
                      size="small"
                      :type="
                        image.execution_status === 'failed' ? 'danger' : 'info'
                      "
                      >{{
                        image.execution_status === "queued" && image.error_code
                          ? "等待自动重试"
                          : executionLabels[image.execution_status]
                      }}</ui-tag
                    ><ui-tag
                      v-if="image.execution_status === 'succeeded'"
                      size="small"
                      :type="
                        image.review_status === 'approved'
                          ? 'success'
                          : 'warning'
                      "
                      >{{ reviewLabels[image.review_status] }}</ui-tag
                    >
                  </div>
                  <div
                    v-if="image.execution_status === 'succeeded'"
                    class="candidate-summary"
                  >
                    <small
                      >{{ image.candidates.length }} 个候选框<span
                        v-if="image.original_count === 0"
                      >
                        · 模型未发现目标</span
                      ><span v-else-if="!image.candidates.length">
                        · 已删除全部候选</span
                      ></small
                    >
                    <small
                      class="token-metrics"
                      :title="metricsTooltip(image)"
                      :aria-label="`输入 ${tokenNumber(image.inference_metrics?.input_tokens)} Token，输出 ${tokenNumber(image.inference_metrics?.output_tokens)} Token，${tpsNumber(image.inference_metrics?.tps)} TPS`"
                    >
                      输入
                      {{ tokenNumber(image.inference_metrics?.input_tokens) }} /
                      输出
                      {{ tokenNumber(image.inference_metrics?.output_tokens) }}
                      <span class="metric-separator">·</span>
                      {{ tpsNumber(image.inference_metrics?.tps) }} TPS
                    </small>
                  </div>
                  <small
                    v-if="image.error_message"
                    class="image-error"
                    :title="image.error_message"
                    >{{ image.error_message }}</small
                  >
                </div>
              </ui-button>
              <div v-if="selectedTaskId" class="image-card-actions">
                <ui-button link type="primary" @click="openTrace(image)"
                  >推理详情</ui-button
                ><ui-button
                  v-if="canRetryImage(image)"
                  link
                  type="warning"
                  :loading="retryingImages.has(image.id)"
                  @click="retryImage(image)"
                  >重试此图</ui-button
                >
              </div>
            </article>
          </div>
          <ui-pagination
            v-model:current-page="page"
            :total="total"
            :page-size="pageSize"
            layout="prev,pager,next,total"
            @current-change="loadImages()"
          />
        </section>
      </div>
    </div>
    <ui-dialog v-model="traceOpen" title="推理详情" width="min(1250px,96vw)"
      ><PreannotationTrace
        v-if="traceOpen"
        :context="traceContext"
        embedded
        @close="traceOpen = false"
    /></ui-dialog>
    <PreannotationProfileDialog
      v-model="profileDialog"
      :profile="editingProfile"
      @saved="profileSaved"
    />
    <PreannotationPromptHistory
      v-model="promptHistoryOpen"
      :dataset-id="datasetId"
      @fill="fillPrompt"
      @closed="focusPrompt"
    />
  </div>
</template>

<style scoped>
.preannotation-page {
  width: 100%;
  min-width: 0;
  color: #263445;
}
section {
  background: white;
  border: 1px solid #e6eaf0;
  border-radius: 12px;
  padding: var(--space-5);
  margin-top: var(--space-5);
}
.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.section-title h2 {
  font-size: 18px;
  margin: 0;
}
.section-title > span {
  font-size: 13px;
  color: #64748b;
}
.prompt-form-item :deep(.ui-form-item__label) {
  width: 100%;
}
.prompt-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
}
.prompt-fill-feedback {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  width: 100%;
  color: #72869e;
  font-size: 12px;
  margin-top: 7px;
}
.batch-prompt-cell {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}
.batch-prompt-cell > span {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.batch-prompt-cell .ui-button {
  flex-shrink: 0;
}
.config-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 0.7fr) minmax(0, 1fr);
  gap: var(--space-5);
}
.config-grid :deep(.ui-select) {
  width: 100%;
}
.interface-picker {
  display: grid;
  grid-template-columns: minmax(0, 1fr) repeat(3, 35px);
  align-items: center;
  width: 100%;
  gap: 6px;
}
.interface-picker .ui-select {
  min-width: 0;
}
.interface-picker > .interface-action {
  width: 35px;
  height: 35px;
  min-height: 35px;
  padding: 0;
}
.generation-actions {
  display: flex;
  gap: var(--space-3);
  align-items: center;
  flex-wrap: wrap;
}
.generation-actions small {
  color: #64748b;
}
.filters {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: var(--space-5);
}
.filters .ui-select {
  width: 170px;
}
.filters .ui-select:first-child {
  width: 250px;
}
.filters > span {
  margin-left: auto;
  color: #64748b;
}
.image-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}
.image-card-wrap {
  border: 1px solid #e3e8ee;
  border-radius: 8px;
  overflow: hidden;
  background: white;
  min-width: 0;
}
.image-card-actions {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding: 0 var(--space-4) var(--space-4);
}
.image-card {
  width: 100%;
  display: block;
  text-align: left;
  padding: 0;
  border: 0;
  border-radius: 0;
  overflow: hidden;
  background: white;
  cursor: pointer;
  color: inherit;
  transition: none;
}
.image-card:hover {
  background: white;
  color: inherit;
  box-shadow: none;
}
.image-card-body {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.image-card-body > .candidate-summary {
  align-items: center;
  gap: 6px var(--space-3);
}
.token-metrics {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  white-space: normal;
  overflow-wrap: anywhere;
}
.metric-separator {
  color: #b1bcc9;
  padding: 0 2px;
}
.image-card strong {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.image-card-body > div {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}
.image-card small {
  color: #64748b;
  line-height: 1.5;
}
.image-card .image-error {
  color: #c24141;
  max-height: 40px;
  overflow: hidden;
}
.ui-pagination {
  justify-content: center;
  margin-top: var(--space-5);
}
.tasks-panel :deep(.ui-table__row) {
  cursor: pointer;
}
@media (max-width: 1000px) {
  .image-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .config-grid {
    grid-template-columns: 1fr 1fr;
  }
  .config-grid > div:first-child {
    grid-column: 1/-1;
  }
}
@media (max-width: 650px) {
  .preannotation-page {
    padding: 0;
  }
  .image-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-3);
  }
  .config-grid {
    grid-template-columns: 1fr;
  }
  .config-grid > div:first-child {
    grid-column: auto;
  }
  section {
    padding: var(--space-4);
  }
  .filters .ui-select,
  .filters .ui-select:first-child {
    width: calc(50% - 6px);
  }
  .section-title > span {
    display: none;
  }
}
.preannotation-layout {
  display: grid;
  grid-template-columns: minmax(280px, 330px) minmax(0, 1fr);
  gap: var(--space-5);
  align-items: start;
}
.generation-rail {
  min-width: 0;
}
.preannotation-results {
  min-width: 0;
}
.preannotation-layout section {
  margin-top: 0;
  margin-bottom: var(--space-5);
  padding: var(--space-5);
}
.generation-rail .config-grid {
  grid-template-columns: 1fr;
  gap: 0;
}
.generation-rail .config-grid > div:first-child {
  grid-column: auto;
}
.generation-rail .generation-actions {
  gap: var(--space-3);
}
.generation-rail .generation-actions > small {
  font-size: 10px;
  line-height: 1.8;
}
.generation-rail .generation-actions > .ui-button {
  flex: 1 1 40%;
}
.generation-rail .generation-actions > .ui-button--primary {
  flex-basis: 100%;
}
.generation-rail .section-title h2 {
  font-size: 14px;
}
.generation-rail .section-title > span {
  display: none;
}
.preannotation-results .section-title h2 {
  font-size: 14px;
}
.preannotation-results .image-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.preannotation-results .filters {
  gap: var(--space-2);
  flex-wrap: nowrap;
  overflow-x: auto;
}
.preannotation-results .filters .ui-select {
  width: auto;
  flex: 1 0 120px;
}
.preannotation-results .filters .ui-select:first-child {
  flex: 1.5 0 180px;
}
.preannotation-results .filters > span {
  flex: none;
  white-space: nowrap;
}
.results-display {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.preannotation-results .image-card strong {
  font-size: 11px;
}
.preannotation-results .image-card-body {
  padding: var(--space-3);
}
.preannotation-results .image-card small {
  font-size: 10px;
}
.preannotation-results .candidate-summary {
  align-items: flex-start;
}
.generation-rail .ui-input[type="textarea"] {
  min-height: 160px;
}
.preannotation-results .ui-table-wrap {
  border: 0;
}
.tasks-panel :deep(.ui-table) {
  table-layout: fixed;
  min-width: 980px;
}
.generation-panel :deep(textarea) {
  min-height: 155px;
}
.tasks-panel :deep(th),
.tasks-panel :deep(td) {
  padding: var(--space-3);
  font-size: 10px;
}
@media (max-width: 1300px) {
  .preannotation-layout {
    grid-template-columns: minmax(250px, 290px) minmax(0, 1fr);
    gap: var(--space-4);
  }
  .preannotation-results .image-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 1000px) {
  .preannotation-layout {
    grid-template-columns: 1fr;
  }
  .generation-rail .config-grid {
    grid-template-columns: 1fr 1fr;
    gap: 0 var(--space-4);
  }
  .generation-rail .config-grid > div:first-child {
    grid-column: 1/-1;
  }
  .generation-rail .generation-actions > .ui-button--primary {
    flex-basis: auto;
  }
  .generation-rail .generation-actions > .ui-button {
    flex: initial;
  }
  .preannotation-results .image-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .generation-rail .config-grid {
    grid-template-columns: 1fr;
  }
  .preannotation-results .image-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .section-title {
    flex-wrap: wrap;
  }
  .results-display {
    width: 100%;
  }
}
</style>
