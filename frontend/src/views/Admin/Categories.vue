<script setup>
import { ref, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { message, messageBox } from "../../shared/ui/feedback";
import api from "../../utils/api";
import { useQueryClient } from "@tanstack/vue-query";
const queryClient = useQueryClient();
import DatasetHeader from "../../components/DatasetHeader.vue";
import {
  parseCategoryKeys,
  eventShortcut,
  categoryShortcutConflict,
  reservedCategoryKeys,
} from "../../features/annotation/domain/shortcuts";
import { Upload } from "@lucide/vue";

const route = useRoute();
const router = useRouter();

const datasetId = computed(() => parseInt(route.params.datasetId));
const dataset = ref(null);
const categories = ref([]);
const capturing = ref(false),
  loadError = ref(false);
const keys = computed(() => parseCategoryKeys(form.value.shortcut_key));
function captureKey(e) {
  e.preventDefault();
  const key = eventShortcut(e);
  if (!key) return;
  if (reservedCategoryKeys.includes(key))
    return message.warning("该快捷键用于工作台操作，请选择其他按键");
  const next = [...new Set([...keys.value, key])];
  if (next.join(",").length > 10)
    return message.warning("当前服务的快捷键字段最多支持 10 个字符");
  const conflict = categoryShortcutConflict(
    categories.value,
    form.value.id,
    next,
  );
  if (conflict) return message.warning(`快捷键已被 ${conflict.name} 使用`);
  form.value.shortcut_key = next.join(",");
  capturing.value = false;
}
function removeKey(key) {
  form.value.shortcut_key = keys.value.filter((k) => k !== key).join(",");
}
const allDatasets = ref([]);
const loading = ref(true);
const dialogVisible = ref(false);
const isEdit = ref(false);
const importDialogVisible = ref(false);
const selectedSourceDataset = ref(null);
const batchTextDialogVisible = ref(false);
const batchText = ref("");
const batchImageDialogVisible = ref(false);
const batchImageFiles = ref([]);
const batchImageUploading = ref(false);

const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem("robomark-token")}`,
}));

const colorOptions = [
  "#FF0000",
  "#00FF00",
  "#0000FF",
  "#FFFF00",
  "#FF00FF",
  "#00FFFF",
  "#FF8000",
  "#8000FF",
  "#0080FF",
  "#FF0080",
  "#80FF00",
  "#00FF80",
];

const form = ref({
  id: null,
  dataset_id: datasetId.value,
  name: "",
  shortcut_key: "",
  color: "#FF0000",
  sort_order: 0,
});

onMounted(async () => {
  await loadData();
});

async function loadData() {
  loading.value = true;
  loadError.value = false;
  try {
    const [datasetRes, categoriesRes, datasetsRes] = await Promise.all([
      api.get(`/datasets/${datasetId.value}`),
      api.get(`/categories/dataset/${datasetId.value}`),
      api.get("/datasets"),
    ]);
    dataset.value = datasetRes.data;
    categories.value = categoriesRes.data;
    queryClient.setQueryData(
      ["categories", datasetId.value],
      categoriesRes.data,
    );
    // 过滤掉当前数据集
    allDatasets.value = datasetsRes.data.filter(
      (d) => d.id !== datasetId.value,
    );
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
}

function showCreateDialog() {
  isEdit.value = false;
  form.value = {
    id: null,
    dataset_id: datasetId.value,
    name: "",
    shortcut_key: "",
    color: colorOptions[categories.value.length % colorOptions.length],
    sort_order: categories.value.length,
  };
  dialogVisible.value = true;
}

function showEditDialog(category) {
  isEdit.value = true;
  form.value = { ...category };
  dialogVisible.value = true;
}

async function handleSubmit() {
  if (!form.value.name) {
    message.warning("请填写类别名称");
    return;
  }

  const conflict = categoryShortcutConflict(
    categories.value,
    form.value.id,
    keys.value,
  );
  if (conflict) return message.warning(`快捷键与 ${conflict.name} 冲突`);
  if (keys.value.some((key) => reservedCategoryKeys.includes(key)))
    return message.warning("快捷键与工作台操作冲突");
  try {
    if (isEdit.value) {
      await api.put(`/categories/${form.value.id}`, form.value);
      message.success("更新成功");
    } else {
      await api.post("/categories", form.value);
      message.success("创建成功");
    }
    dialogVisible.value = false;
    loadData();
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

async function handleDelete(category) {
  try {
    await messageBox.confirm(
      `确定要删除类别 "${category.name}" 吗？相关的标注将被清除。`,
      "警告",
      { type: "warning" },
    );

    await api.delete(`/categories/${category.id}`);
    message.success("删除成功");
    loadData();
  } catch (error) {
    if (error !== "cancel") {
      // 错误已在拦截器中处理
    }
  }
}

function showImportDialog() {
  selectedSourceDataset.value = null;
  importDialogVisible.value = true;
}

async function handleImportFromDataset() {
  if (!selectedSourceDataset.value) {
    message.warning("请选择源数据集");
    return;
  }

  try {
    const response = await api.post(
      `/categories/import-from-dataset/${datasetId.value}`,
      {
        source_dataset_id: selectedSourceDataset.value,
      },
    );
    message.success(response.data.message);
    importDialogVisible.value = false;
    loadData();
  } catch (error) {
    message.error(error.response?.data?.detail || "导入失败");
  }
}

async function handleImportFromConfig() {
  try {
    const response = await api.post(
      `/dataset-configs/${datasetId.value}/import-default-categories`,
    );
    message.success(response.data.message);
    loadData();
  } catch (error) {
    message.error(error.response?.data?.detail || "导入失败");
  }
}

function handleImportCommand(command) {
  if (command === "dataset") {
    showImportDialog();
  } else if (command === "config") {
    handleImportFromConfig();
  } else if (command === "text") {
    batchText.value = "";
    batchTextDialogVisible.value = true;
  } else if (command === "images") {
    batchImageFiles.value = [];
    batchImageDialogVisible.value = true;
  }
}

async function handleBatchTextImport() {
  if (!batchText.value.trim()) {
    message.warning("请输入类别名称");
    return;
  }
  try {
    const response = await api.post(
      `/categories/batch-text/${datasetId.value}`,
      {
        text: batchText.value,
      },
    );
    message.success(`成功导入 ${response.data.length} 个类别`);
    batchTextDialogVisible.value = false;
    batchText.value = "";
    loadData();
  } catch (error) {
    message.error(error.response?.data?.detail || "导入失败");
  }
}

function handleUploadSuccess() {
  message.success("模板图片上传成功");
  loadData();
}

function handleUploadError() {
  message.error("模板图片上传失败");
}

async function handleDeleteTemplateImage(category) {
  try {
    await api.delete(`/categories/${category.id}/template-image`);
    message.success("模板图片已删除");
    loadData();
  } catch (error) {
    message.error(error.response?.data?.detail || "删除失败");
  }
}

function handleBatchImageChange(uploadFile, uploadFiles) {
  batchImageFiles.value = uploadFiles;
}

function handleBatchImageRemove(uploadFile, uploadFiles) {
  batchImageFiles.value = uploadFiles;
}

async function handleBatchImageImport() {
  if (batchImageFiles.value.length === 0) {
    message.warning("请选择图片文件");
    return;
  }

  batchImageUploading.value = true;
  try {
    const formData = new FormData();
    batchImageFiles.value.forEach((file) => {
      formData.append("files", file.raw);
    });
    const response = await api.post(
      `/categories/batch-images/${datasetId.value}`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      },
    );
    message.success(response.data.message);
    batchImageDialogVisible.value = false;
    batchImageFiles.value = [];
    loadData();
  } catch (error) {
    message.error(error.response?.data?.detail || "导入失败");
  } finally {
    batchImageUploading.value = false;
  }
}
</script>

<template>
  <div class="categories-page" v-loading="loading">
    <DatasetHeader
      :dataset-id="datasetId"
      :dataset="dataset"
      :loading="loading"
    />
    <div class="section-heading category-toolbar">
      <div>
        <h2>类别与模板</h2>
        <p>管理目标类别、颜色、快捷键与图片模板。</p>
      </div>
      <div class="category-actions">
        <ui-dropdown @command="handleImportCommand" trigger="click">
          <ui-button>
            导入类别 <ui-icon name="ArrowDown" :size="14" />
          </ui-button>
          <template #dropdown>
            <ui-dropdown-menu>
              <ui-dropdown-item command="dataset"
                >从其他数据集导入</ui-dropdown-item
              >
              <ui-dropdown-item command="config"
                >从格式配置导入</ui-dropdown-item
              >
              <ui-dropdown-item command="text">批量文本导入</ui-dropdown-item>
              <ui-dropdown-item command="images">批量图片导入</ui-dropdown-item>
            </ui-dropdown-menu>
          </template>
        </ui-dropdown>
        <ui-button type="primary" @click="showCreateDialog" :icon="'Plus'">
          添加类别
        </ui-button>
      </div>
    </div>

    <ui-alert v-if="loadError" type="error" title="类别加载失败"
      ><ui-button @click="loadData">重新加载</ui-button></ui-alert
    >
    <div class="categories-grid">
      <ui-card
        as="article"
        v-for="category in categories"
        :key="category.id"
        class="category-card"
      >
        <div class="color-bar" :style="{ background: category.color }"></div>
        <div class="card-content">
          <div class="category-card-header">
            <h3 :title="category.name">{{ category.name }}</h3>
            <div
              class="category-card-actions"
              role="group"
              :aria-label="`${category.name} 的操作`"
            >
              <ui-upload
                :action="`/api/categories/${category.id}/template-image`"
                :headers="uploadHeaders"
                :show-file-list="false"
                :on-success="handleUploadSuccess"
                :on-error="handleUploadError"
                accept="image/*"
              >
                <ui-button
                  class="category-action"
                  variant="ghost"
                  circle
                  :icon="Upload"
                  :title="
                    category.template_image_path ? '更换模板' : '上传模板'
                  "
                  :aria-label="`${category.template_image_path ? '更换' : '上传'}${category.name}的模板`"
                />
              </ui-upload>
              <ui-button
                class="category-action"
                variant="ghost"
                circle
                icon="ImageOff"
                title="删除模板"
                :aria-label="`删除${category.name}的模板`"
                :disabled="!category.template_image_path"
                @click="handleDeleteTemplateImage(category)"
              />
              <ui-button
                class="category-action"
                variant="ghost"
                circle
                icon="Pencil"
                title="编辑类别"
                :aria-label="`编辑类别${category.name}`"
                @click="showEditDialog(category)"
              />
              <ui-button
                class="category-action"
                type="danger"
                circle
                icon="Delete"
                title="删除类别"
                :aria-label="`删除类别${category.name}`"
                @click="handleDelete(category)"
              />
            </div>
          </div>
          <div class="template-preview">
            <img
              v-if="category.template_image_path"
              :src="`/api/categories/${category.id}/template-image`"
              :alt="`${category.name}的模板图片`"
              loading="lazy"
              decoding="async"
            />
            <div v-else class="template-placeholder">
              <ui-icon name="Image" :size="22" /><span>未设置模板</span>
            </div>
          </div>
          <div class="category-meta">
            <span class="order">排序 {{ category.sort_order }}</span>
            <span v-if="category.shortcut_key" class="category-shortcuts"
              ><span>快捷键</span
              ><ui-kbd
                v-for="key in parseCategoryKeys(category.shortcut_key)"
                :key="key"
                >{{ key }}</ui-kbd
              ></span
            >
            <span v-else class="shortcut-empty">未设置快捷键</span>
          </div>
        </div>
      </ui-card>

      <ui-button
        v-if="categories.length === 0"
        variant="ghost"
        class="empty-card"
        @click="showCreateDialog"
      >
        <ui-icon :size="32"><Plus /></ui-icon>
        <span>添加第一个类别</span>
      </ui-button>
    </div>

    <!-- 编辑对话框 -->
    <ui-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑类别' : '添加类别'"
      width="400px"
    >
      <ui-form :model="form" label-width="80px">
        <ui-form-item label="名称" required>
          <ui-input v-model="form.name" placeholder="类别名称" />
        </ui-form-item>
        <ui-form-item label="快捷键">
          <div class="category-key-editor">
            <ui-button
              v-for="key in keys"
              :key="key"
              size="small"
              @click="removeKey(key)"
              >{{ key }} ×</ui-button
            ><ui-button
              variant="outline"
              :class="{ capturing }"
              @click="capturing = true"
              @keydown="capturing && captureKey($event)"
              >{{ capturing ? "请按下快捷键…" : "添加快捷键" }}</ui-button
            >
          </div>
          <p class="form-tip">
            点击添加后按键，支持多个快捷键与组合键。点击已有按键可移除。
          </p>
        </ui-form-item>
        <ui-form-item label="颜色">
          <div class="color-picker">
            <ui-button
              variant="ghost"
              v-for="color in colorOptions"
              :key="color"
              class="color-option"
              :aria-label="`选择颜色 ${color}`"
              :class="{ active: form.color === color }"
              :style="{ background: color }"
              @click="form.color = color"
            />
          </div>
        </ui-form-item>
        <ui-form-item label="排序">
          <ui-input-number v-model="form.sort_order" :min="0" :max="100" />
        </ui-form-item>
      </ui-form>
      <template #footer>
        <ui-button @click="dialogVisible = false">取消</ui-button>
        <ui-button type="primary" @click="handleSubmit">确定</ui-button>
      </template>
    </ui-dialog>

    <!-- 从数据集导入对话框 -->
    <ui-dialog
      v-model="importDialogVisible"
      title="从其他数据集导入类别"
      width="400px"
    >
      <ui-form label-width="100px">
        <ui-form-item label="源数据集">
          <ui-select
            v-model="selectedSourceDataset"
            placeholder="选择数据集"
            style="width: 100%"
          >
            <ui-option
              v-for="ds in allDatasets"
              :key="ds.id"
              :value="ds.id"
              :label="ds.name"
            />
          </ui-select>
        </ui-form-item>
        <div class="form-tip" style="margin-left: 100px">
          已存在的类别名称将被跳过
        </div>
      </ui-form>
      <template #footer>
        <ui-button @click="importDialogVisible = false">取消</ui-button>
        <ui-button type="primary" @click="handleImportFromDataset"
          >导入</ui-button
        >
      </template>
    </ui-dialog>

    <!-- 批量文本导入对话框 -->
    <ui-dialog
      v-model="batchTextDialogVisible"
      title="批量导入类别"
      width="450px"
    >
      <ui-form label-width="100px">
        <ui-form-item label="类别列表">
          <ui-input
            v-model="batchText"
            type="textarea"
            :rows="12"
            placeholder="每行一个类别名称，例如：&#10;hero&#10;infantry&#10;engineer&#10;sentry&#10;drone"
          />
        </ui-form-item>
        <div class="form-tip" style="margin-left: 100px">
          每行一个类别名称，颜色自动分配，重复名称自动跳过
        </div>
      </ui-form>
      <template #footer>
        <ui-button @click="batchTextDialogVisible = false">取消</ui-button>
        <ui-button type="primary" @click="handleBatchTextImport"
          >导入</ui-button
        >
      </template>
    </ui-dialog>

    <!-- 批量图片导入对话框 -->
    <ui-dialog
      v-model="batchImageDialogVisible"
      title="批量图片导入类别"
      width="500px"
    >
      <div class="batch-image-tip">
        图片文件名（不含扩展名）将作为类别名称，图片自动设为类别模板。
      </div>
      <ui-upload
        v-model:file-list="batchImageFiles"
        :auto-upload="false"
        accept="image/*"
        multiple
        :on-change="handleBatchImageChange"
        :on-remove="handleBatchImageRemove"
        list-type="picture"
      >
        <ui-button type="primary">选择图片</ui-button>
        <template #tip>
          <div class="form-tip">
            支持 jpg/png/bmp/webp，可多选。重复名称自动跳过。
          </div>
        </template>
      </ui-upload>
      <template #footer>
        <ui-button @click="batchImageDialogVisible = false">取消</ui-button>
        <ui-button
          type="primary"
          :loading="batchImageUploading"
          :disabled="batchImageFiles.length === 0"
          @click="handleBatchImageImport"
        >
          导入 ({{ batchImageFiles.length }} 张)
        </ui-button>
      </template>
    </ui-dialog>
  </div>
</template>

<style scoped>
.category-toolbar {
  flex-wrap: wrap;
}
.category-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.categories-page {
  min-width: 0;
}

.categories-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}
.category-card {
  min-width: 0;
}
.color-bar {
  height: 3px;
}
.card-content {
  padding: 14px;
}
.category-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}
.category-card-header h3 {
  margin: 0;
  font-size: 14px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.category-card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: none;
}
.category-card-actions :deep(.ui-upload),
.category-card-actions :deep(.ui-upload > div) {
  display: flex;
  align-items: center;
}
.category-card-actions :deep(.category-action) {
  width: 28px;
  height: 28px;
  min-height: 28px;
  padding: 0;
  border-radius: 6px;
}
.template-preview {
  display: grid;
  place-items: center;
  height: 100px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--surface-muted);
}
.template-preview img {
  display: block;
  width: 100%;
  height: 100px;
  object-fit: contain;
}
.template-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
  color: var(--muted);
  font-size: 10px;
}
.template-placeholder :deep(svg) {
  color: #a2abba;
}
.category-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 20px;
  margin-top: 10px;
  font-size: 10px;
  color: var(--muted);
}
.order {
  white-space: nowrap;
}
.category-shortcuts {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}
.shortcut-empty {
  color: #9ba3b1;
}

.empty-card {
  border: 2px dashed #ddd;
  border-radius: 8px;
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #999;
  cursor: pointer;
  transition: all 0.2s;
}

.empty-card:hover {
  border-color: #409eff;
  color: #409eff;
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.color-picker {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.color-option {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.color-option:hover {
  transform: scale(1.1);
}

.color-option.active {
  border-color: #333;
}

.batch-image-tip {
  color: #666;
  font-size: 13px;
  margin-bottom: 16px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
}
.category-key-editor {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.category-key-editor .capturing {
  border-color: var(--primary);
  color: var(--primary);
}
.color-picker .color-option {
  min-height: 26px;
  width: 26px;
  padding: 0;
}
.empty-card {
  display: flex;
  flex-direction: column;
  min-height: 170px;
}
</style>
