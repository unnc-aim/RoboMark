<script setup>
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { message } from "../../shared/ui/feedback";
import api, { apiFetch, reportError } from "../../utils/api";
import { getErrorMessage } from "../../utils/apiErrors";
import { readImportProgress } from "../../utils/importProgress";
import DatasetCard from "../../components/DatasetCard.vue";
import DirectoryPicker from "../../components/DirectoryPicker.vue";
import { useQueryClient } from "@tanstack/vue-query";
const queryClient = useQueryClient();
const search = ref(""),
  status = ref("all"),
  layout = ref("grid");
const filtered = computed(() =>
  datasets.value.filter(
    (d) =>
      `${d.name} ${d.description || ""}`
        .toLowerCase()
        .includes(search.value.toLowerCase()) &&
      (status.value === "all" ||
        (status.value === "done"
          ? d.total_images > 0 && d.labeled_images >= d.total_images
          : d.labeled_images < d.total_images)),
  ),
);

const router = useRouter();

const datasets = ref([]);
const loading = ref(true);
const dialogVisible = ref(false);
const dialogTitle = ref("创建数据集");
const isEdit = ref(false);

const form = ref({
  id: null,
  name: "",
  description: "",
  image_path: "",
  label_path: "",
});

// 批量导入相关
const batchImportVisible = ref(false);
const loadError = ref(false);
const batchImportForm = ref({
  root_path: "",
});
const batchImportProgress = ref({
  status: "",
  message: "",
  total_folders: 0,
  processed_folders: 0,
  datasets_created: 0,
  total_images_imported: 0,
  current_folder: "",
});
const isImporting = ref(false);

onMounted(() => {
  loadDatasets();
  if (router.currentRoute.value.query.create === "1") showCreateDialog();
});

async function loadDatasets() {
  loading.value = true;
  loadError.value = false;
  try {
    const response = await api.get("/datasets");
    datasets.value = response.data;
    queryClient.invalidateQueries({ queryKey: ["datasets"] });
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
}

function showCreateDialog() {
  isEdit.value = false;
  dialogTitle.value = "创建数据集";
  form.value = {
    id: null,
    name: "",
    description: "",
    image_path: "",
    label_path: "",
  };
  dialogVisible.value = true;
}

async function handleSubmit() {
  if (!form.value.name || !form.value.image_path) {
    message.warning("请填写必填字段");
    return;
  }

  try {
    if (isEdit.value) {
      await api.put(`/datasets/${form.value.id}`, form.value);
      message.success("更新成功");
    } else {
      await api.post("/datasets", form.value);
      message.success("创建成功");
    }
    dialogVisible.value = false;
    loadDatasets();
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

function showBatchImportDialog() {
  batchImportForm.value = {
    root_path: "",
  };
  batchImportProgress.value = {
    status: "",
    message: "",
    total_folders: 0,
    processed_folders: 0,
    datasets_created: 0,
    total_images_imported: 0,
    current_folder: "",
  };
  isImporting.value = false;
  batchImportVisible.value = true;
}

async function startBatchImport() {
  if (isImporting.value) return;
  if (!batchImportForm.value.root_path) {
    message.warning("请填写根目录路径");
    return;
  }

  isImporting.value = true;
  batchImportProgress.value = {
    status: "scanning",
    message: "正在扫描目录...",
    total_folders: 0,
    processed_folders: 0,
    datasets_created: 0,
    total_images_imported: 0,
    current_folder: "",
  };

  try {
    const response = await apiFetch("/api/datasets/batch-import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(batchImportForm.value),
    });
    await readImportProgress(response.body, (data) => {
      batchImportProgress.value = { ...batchImportProgress.value, ...data };
    });
    message.success(batchImportProgress.value.message);
    await loadDatasets();
  } catch (error) {
    batchImportProgress.value.status = "error";
    batchImportProgress.value.message = await getErrorMessage(error, "批量导入失败");
    await reportError(error, "批量导入失败");
  } finally {
    isImporting.value = false;
  }
}

function closeBatchImportDialog() {
  if (isImporting.value) {
    message.warning("正在导入中，请等待完成");
    return;
  }
  batchImportVisible.value = false;
}
</script>

<template>
  <div class="datasets-page">
    <header class="page-heading">
      <div>
        <h1>数据集工作区</h1>
        <p>管理图像、标注和推理任务。选择一个数据集继续工作。</p>
      </div>
      <div class="page-heading-actions">
        <ui-button icon="Upload" @click="showBatchImportDialog"
          >批量导入</ui-button
        ><ui-button type="primary" icon="Plus" @click="showCreateDialog"
          >新建数据集</ui-button
        >
      </div>
    </header>
    <div class="summary-strip">
      <span
        ><strong>{{ datasets.length }}</strong> 个数据集</span
      ><span
        ><strong>{{
          datasets.reduce((s, d) => s + d.total_images, 0).toLocaleString()
        }}</strong>
        张图片</span
      ><span
        ><strong>{{
          datasets.reduce((s, d) => s + d.labeled_images, 0).toLocaleString()
        }}</strong>
        张已标注</span
      >
    </div>
    <div class="collection-toolbar">
      <ui-radio-group v-model="status" aria-label="数据集状态"
        ><ui-radio-button value="all">全部数据集</ui-radio-button
        ><ui-radio-button value="active">进行中</ui-radio-button
        ><ui-radio-button value="done">已完成</ui-radio-button></ui-radio-group
      >
      <div class="collection-controls">
        <ui-input
          v-model="search"
          prefix-icon="Search"
          placeholder="搜索数据集…"
        /><ui-radio-group v-model="layout" aria-label="布局"
          ><ui-radio-button value="grid" aria-label="网格视图"
            ><ui-icon name="LayoutGrid" /></ui-radio-button
          ><ui-radio-button value="list" aria-label="列表视图"
            ><ui-icon name="List" /></ui-radio-button
        ></ui-radio-group>
      </div>
    </div>
    <ui-alert v-if="loadError" type="error" title="数据集加载失败"
      ><ui-button @click="loadDatasets">重新加载</ui-button></ui-alert
    >
    <div
      v-loading="loading"
      class="dataset-collection"
      :class="{ 'list-view': layout === 'list' }"
    >
      <DatasetCard
        v-for="dataset in filtered"
        :key="dataset.id"
        :dataset="dataset"
        :list="layout === 'list'"
      />
    </div>
    <ui-empty
      v-if="!loading && !loadError && !filtered.length"
      :description="search ? '没有匹配的数据集' : '还没有数据集'"
      ><ui-button type="primary" @click="showCreateDialog"
        >创建数据集</ui-button
      ></ui-empty
    >

    <!-- 创建/编辑对话框 -->
    <ui-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <ui-form :model="form" label-width="100px">
        <ui-form-item label="名称" required>
          <ui-input v-model="form.name" placeholder="数据集名称" />
        </ui-form-item>
        <ui-form-item label="描述">
          <ui-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="数据集描述"
          />
        </ui-form-item>
        <ui-form-item label="图片路径" required>
          <DirectoryPicker v-model="form.image_path" label="图片目录" />
          <div class="form-tip">服务器上的图片目录绝对路径</div>
        </ui-form-item>
        <ui-form-item label="标签路径">
          <DirectoryPicker v-model="form.label_path" label="标签目录" />
          <div class="form-tip">YOLO标签保存目录（可选）</div>
        </ui-form-item>
      </ui-form>
      <template #footer>
        <ui-button @click="dialogVisible = false">取消</ui-button>
        <ui-button type="primary" @click="handleSubmit">确定</ui-button>
      </template>
    </ui-dialog>

    <!-- 批量导入对话框 -->
    <ui-dialog
      v-model="batchImportVisible"
      title="批量导入数据集"
      width="550px"
      :close-on-click-modal="!isImporting"
      :close-on-press-escape="!isImporting"
      :show-close="!isImporting"
      @close="closeBatchImportDialog"
    >
      <ui-form
        :model="batchImportForm"
        label-width="100px"
        :disabled="isImporting"
      >
        <ui-form-item label="根目录" required>
          <DirectoryPicker v-model="batchImportForm.root_path" label="根目录" />
          <div class="form-tip">
            递归扫描所有 image/images 文件夹，labels 自动创建在同级目录
          </div>
        </ui-form-item>
      </ui-form>

      <!-- 进度显示 -->
      <div v-if="batchImportProgress.status" class="import-progress">
        <ui-divider />
        <div class="progress-info">
          <div class="progress-status">
            <ui-icon
              v-if="
                batchImportProgress.status === 'scanning' ||
                batchImportProgress.status === 'importing'
              "
              class="is-loading"
            >
              <i class="el-icon-loading"></i>
            </ui-icon>
            <ui-tag v-if="batchImportProgress.status === 'done'" type="success"
              >完成</ui-tag
            >
            <ui-tag
              v-else-if="batchImportProgress.status === 'error'"
              type="danger"
              >错误</ui-tag
            >
            <ui-tag v-else type="info">{{
              batchImportProgress.status === "scanning" ? "扫描中" : "导入中"
            }}</ui-tag>
          </div>
          <div class="progress-message">{{ batchImportProgress.message }}</div>
        </div>

        <div
          v-if="batchImportProgress.total_folders > 0"
          class="progress-detail"
        >
          <ui-progress
            :percentage="
              Math.round(
                (batchImportProgress.processed_folders /
                  batchImportProgress.total_folders) *
                  100,
              )
            "
            :status="
              batchImportProgress.status === 'done'
                ? 'success'
                : batchImportProgress.status === 'error'
                  ? 'exception'
                  : ''
            "
          />
          <div class="progress-stats">
            <span
              >文件夹: {{ batchImportProgress.processed_folders }} /
              {{ batchImportProgress.total_folders }}</span
            >
            <span>创建数据集: {{ batchImportProgress.datasets_created }}</span>
            <span
              >导入图片: {{ batchImportProgress.total_images_imported }}</span
            >
          </div>
        </div>

        <div
          v-if="
            batchImportProgress.current_folder &&
            batchImportProgress.status === 'importing'
          "
          class="current-folder"
        >
          当前: {{ batchImportProgress.current_folder }}
        </div>
      </div>

      <template #footer>
        <ui-button @click="closeBatchImportDialog" :disabled="isImporting">
          {{ batchImportProgress.status === "done" ? "关闭" : "取消" }}
        </ui-button>
        <ui-button
          type="primary"
          @click="startBatchImport"
          :loading="isImporting"
          :disabled="batchImportProgress.status === 'done'"
        >
          {{ isImporting ? "导入中..." : "开始导入" }}
        </ui-button>
      </template>
    </ui-dialog>
  </div>
</template>

<style scoped>
.datasets-page {
  min-width: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-5);
}

.page-header h2 {
  margin: 0;
}

.header-buttons {
  display: flex;
  gap: var(--space-3);
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.import-progress {
  margin-top: var(--space-4);
}

.progress-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.progress-status {
  flex-shrink: 0;
}

.progress-message {
  color: #606266;
  font-size: 14px;
}

.progress-detail {
  margin-bottom: var(--space-3);
}

.progress-stats {
  display: flex;
  justify-content: space-between;
  margin-top: var(--space-2);
  font-size: 13px;
  color: #909399;
}

.current-folder {
  font-size: 12px;
  color: #909399;
  padding: var(--space-2);
  background: #f5f7fa;
  border-radius: 4px;
}

.is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
