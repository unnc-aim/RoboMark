<script setup>
import { ref, onMounted, computed, watch } from "vue";
import { message } from "../../shared/ui/feedback";
import api from "../../utils/api";

const loading = ref(false);
const datasets = ref([]);
const formats = ref([]);
const exportResult = ref(null),
  loadingOptions = ref(true),
  optionsError = ref(false);
let exportGeneration = 0;

const form = ref({
  dataset_id: null,
  format: "yolov8",
  output_name: "",
  train_ratio: 0.8,
  val_ratio: 0.1,
  test_ratio: 0.1,
  include_unlabeled: false,
});

watch(
  () => JSON.stringify(form.value),
  () => {
    exportGeneration++;
    exportResult.value = null;
  },
  { flush: "sync" },
);

const currentFormatInfo = computed(() => {
  return formats.value.find((f) => f.id === form.value.format) || {};
});

onMounted(async () => {
  try {
    const [datasetsRes, formatsRes] = await Promise.all([
      api.get("/datasets"),
      api.get("/export/formats"),
    ]);
    datasets.value = datasetsRes.data;
    formats.value = formatsRes.data;
  } catch {
    optionsError.value = true;
  } finally {
    loadingOptions.value = false;
  }
});

async function handleExport() {
  if (!form.value.dataset_id) {
    message.warning("请选择数据集");
    return;
  }

  const total =
    form.value.train_ratio + form.value.val_ratio + form.value.test_ratio;
  if (Math.abs(total - 1) > 0.01) {
    message.warning("分割比例之和必须为1");
    return;
  }

  loading.value = true;
  try {
    const generation = ++exportGeneration;
    const response = await api.post("/export", { ...form.value });
    if (generation !== exportGeneration) return;
    exportResult.value = response.data;
    message.success("导出成功");
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false;
  }
}

async function handleDownload() {
  if (!exportResult.value?.download_url) return;

  try {
    // 使用 axios 下载（带认证）
    const response = await api.get(exportResult.value.download_url, {
      // download_url is already rooted at /api; keep the authenticated interceptor.
      baseURL: "",
      responseType: "blob",
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${form.value.output_name || "dataset"}.zip`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    // Allow the browser to consume the Blob before revoking it.
    window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
  } catch (error) {
    message.error("下载失败");
  }
}

function getDatasetName(id) {
  return datasets.value.find((d) => d.id === id)?.name || "";
}
</script>

<template>
  <div class="export-page">
    <div class="page-header">
      <h2>数据集导出</h2>
    </div>

    <ui-alert
      v-if="optionsError"
      type="error"
      title="导出选项加载失败，请刷新后重试"
    />
    <div class="export-layout">
      <ui-card class="export-form panel-padding" v-loading="loadingOptions"
        ><div class="section-heading"><h3>导出配置</h3></div>
        <ui-form
          :model="form"
          :disabled="loading"
          label-width="120px"
          @submit.prevent="handleExport"
        >
          <ui-form-item label="选择数据集" required>
            <ui-select
              v-model="form.dataset_id"
              placeholder="请选择数据集"
              style="width: 100%"
            >
              <ui-option
                v-for="ds in datasets"
                :key="ds.id"
                :label="`${ds.name} (${ds.labeled_images}/${ds.total_images})`"
                :value="ds.id"
              />
            </ui-select>
          </ui-form-item>

          <ui-form-item label="导出格式" required>
            <div class="format-select">
              <ui-select v-model="form.format" style="width: 100%">
                <ui-option
                  v-for="fmt in formats"
                  :key="fmt.id"
                  :label="fmt.name"
                  :value="fmt.id"
                />
              </ui-select>
              <div class="format-desc" v-if="currentFormatInfo.description">
                {{ currentFormatInfo.description }}
              </div>
            </div>
          </ui-form-item>

          <ui-form-item label="输出名称">
            <ui-input
              v-model="form.output_name"
              placeholder="留空则使用数据集名称"
              style="width: 100%"
            />
          </ui-form-item>

          <ui-form-item label="数据集分割">
            <div class="split-config">
              <div class="split-item">
                <span>训练集</span>
                <ui-input-number
                  v-model="form.train_ratio"
                  aria-label="训练集"
                  id="export-train-ratio"
                  :min="0"
                  :max="1"
                  :step="0.1"
                  :precision="1"
                />
              </div>
              <div class="split-item">
                <span>验证集</span>
                <ui-input-number
                  v-model="form.val_ratio"
                  aria-label="验证集"
                  id="export-val-ratio"
                  :min="0"
                  :max="1"
                  :step="0.1"
                  :precision="1"
                />
              </div>
              <div class="split-item">
                <span>测试集</span>
                <ui-input-number
                  v-model="form.test_ratio"
                  aria-label="测试集"
                  id="export-test-ratio"
                  :min="0"
                  :max="1"
                  :step="0.1"
                  :precision="1"
                />
              </div>
            </div>
          </ui-form-item>

          <ui-form-item label="包含未标注">
            <ui-switch v-model="form.include_unlabeled" />
            <span class="tip">开启后将包含未标注的图片（标签文件为空）</span>
          </ui-form-item>

          <ui-form-item>
            <ui-button type="primary" :loading="loading" @click="handleExport">
              开始导出
            </ui-button>
          </ui-form-item>
        </ui-form>
      </ui-card>
      <ui-card class="panel-padding export-preview"
        ><div class="section-heading"><h3>导出预览</h3></div>
        <ui-empty
          v-if="!exportResult"
          description="提交有效配置后，在此查看导出结果"
          ><span class="form-tip"
            >生成 ZIP 后可查看实际图片数量与标注统计。</span
          ></ui-empty
        >
        <!-- 导出结果 -->
        <div v-if="exportResult" class="export-result">
          <h3>导出完成</h3>
          <div class="result-info">
            <div class="info-grid">
              <div class="info-item">
                <span class="label">数据集</span>
                <span class="value">{{ getDatasetName(form.dataset_id) }}</span>
              </div>
              <div class="info-item">
                <span class="label">导出格式</span>
                <span class="value">{{ exportResult.format }}</span>
              </div>
              <div class="info-item">
                <span class="label">类别数</span>
                <span class="value">{{ exportResult.categories }}</span>
              </div>
              <div class="info-item">
                <span class="label">总图片数</span>
                <span class="value">{{ exportResult.total_images }}</span>
              </div>
              <div class="info-item">
                <span class="label">训练集</span>
                <span class="value">{{ exportResult.train_images }}</span>
              </div>
              <div class="info-item">
                <span class="label">验证集</span>
                <span class="value">{{ exportResult.val_images }}</span>
              </div>
              <div class="info-item">
                <span class="label">测试集</span>
                <span class="value">{{ exportResult.test_images }}</span>
              </div>
              <div class="info-item">
                <span class="label">标注框数</span>
                <span class="value">{{ exportResult.total_annotations }}</span>
              </div>
            </div>

            <ui-button
              type="success"
              size="large"
              @click="handleDownload"
              :icon="'Download'"
            >
              下载 ZIP 文件
            </ui-button>
          </div>
        </div>
      </ui-card>
    </div>
    <!-- 导出格式说明 -->
    <div class="format-info">
      <h3>格式说明</h3>

      <ui-tabs>
        <ui-tab-pane label="YOLOv5/v7/v8">
          <div class="format-content">
            <pre>
dataset/
├── data.yaml          # 配置文件
├── images/
│   ├── train/        # 训练图片
│   ├── val/          # 验证图片
│   └── test/         # 测试图片
└── labels/
    ├── train/        # 训练标签 (.txt)
    ├── val/          # 验证标签
    └── test/         # 测试标签

# 标签格式 (每行一个目标，归一化坐标 0-1)
class_id x_center y_center width height</pre
            >
          </div>
        </ui-tab-pane>

        <ui-tab-pane label="YOLO Darknet">
          <div class="format-content">
            <pre>
dataset/
├── classes.names      # 类别名称列表
├── dataset.data       # 配置文件
├── train.txt          # 训练图片路径列表
├── val.txt            # 验证图片路径列表
├── test.txt           # 测试图片路径列表
├── images/            # 所有图片
└── labels/            # 所有标签 (.txt)

# 标签格式与 YOLOv8 相同
class_id x_center y_center width height</pre
            >
          </div>
        </ui-tab-pane>

        <ui-tab-pane label="COCO JSON">
          <div class="format-content">
            <pre>
dataset/
├── annotations/
│   ├── instances_train.json
│   ├── instances_val.json
│   └── instances_test.json
├── train/             # 训练图片
├── val/               # 验证图片
└── test/              # 测试图片

# JSON 结构
{
  "images": [...],
  "annotations": [...],  # bbox: [x, y, width, height] 像素坐标
  "categories": [...]
}</pre
            >
          </div>
        </ui-tab-pane>
      </ui-tabs>
    </div>
  </div>
</template>

<style scoped>
.export-page {
  min-width: 0;
}

.page-header {
  margin-bottom: var(--space-5);
}

.page-header h2 {
  margin: 0;
}

.export-form {
  margin-bottom: var(--space-6);
}

.split-config {
  display: flex;
  gap: var(--space-5);
}

.split-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.split-item span {
  font-size: 13px;
  color: #666;
}

.tip {
  margin-left: var(--space-3);
  color: #999;
  font-size: 13px;
}

.export-result {
  padding: var(--space-5);
  background: #f0f9eb;
  border-radius: 8px;
  margin-bottom: var(--space-6);
}

.export-result h3 {
  margin-top: 0;
  color: #67c23a;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--space-4);
}

.info-item {
  display: flex;
  flex-direction: column;
}

.info-item .label {
  font-size: 12px;
  color: #999;
}

.info-item .value {
  font-size: 20px;
  font-weight: bold;
  color: #333;
}

.format-info {
  padding: var(--space-5);
  background: #f5f7fa;
  border-radius: 8px;
}

.format-info h3 {
  margin-top: 0;
}

.format-content pre {
  background: #2d2d2d;
  color: #f8f8f2;
  padding: var(--space-4);
  border-radius: 4px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
}

.format-select {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.format-desc {
  font-size: 12px;
  color: #909399;
}
.export-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: var(--space-5);
  align-items: start;
}
.export-form {
  margin-bottom: var(--space-5);
}
.export-preview {
  min-height: 340px;
}
.export-result {
  background: transparent;
  padding: 0;
  margin: 0;
}
.export-result h3 {
  color: var(--success);
  font-size: 15px;
  margin-bottom: var(--space-5);
}
.export-result .info-grid {
  grid-template-columns: 1fr 1fr;
  gap: var(--space-5) var(--space-5);
}
.export-result .info-item .label {
  font-size: 10px;
  color: var(--muted);
}
.export-result .info-item .value {
  font-size: 21px;
  font-weight: 550;
  margin-top: 7px;
  color: var(--foreground);
}
.export-result .result-info {
  gap: var(--space-5);
}
.split-config {
  gap: var(--space-4);
  width: 100%;
}
.split-item {
  flex: 1;
  min-width: 0;
}
.split-item :deep(.ui-number) {
  width: 100%;
}
.tip {
  font-size: 10px;
  margin-left: 0;
  color: var(--muted);
}
.format-info {
  border: 1px solid var(--border);
  background: var(--surface);
  margin-top: 5px;
}
.format-content pre {
  font-size: 11px;
  line-height: 1.9;
  background: #202735;
}
.format-info h3 {
  font-size: 14px;
  margin-bottom: var(--space-4);
}
@media (max-width: 950px) {
  .export-layout {
    grid-template-columns: 1fr;
  }
  .export-preview {
    margin-bottom: var(--space-5);
  }
  .export-form {
    margin-bottom: 0;
  }
}
.split-item span {
  font-size: 11px;
}
.export-result > .result-info > .ui-button {
  width: 100%;
}
</style>
