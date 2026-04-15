<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../utils/api'

const route = useRoute()
const router = useRouter()

const datasetId = computed(() => parseInt(route.params.datasetId))
const dataset = ref(null)
const categories = ref([])
const allDatasets = ref([])
const loading = ref(true)
const dialogVisible = ref(false)
const isEdit = ref(false)
const importDialogVisible = ref(false)
const selectedSourceDataset = ref(null)
const batchTextDialogVisible = ref(false)
const batchText = ref('')
const batchImageDialogVisible = ref(false)
const batchImageFiles = ref([])
const batchImageUploading = ref(false)

const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('torch-markup-token')}`
}))

const colorOptions = [
  '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF',
  '#FF8000', '#8000FF', '#0080FF', '#FF0080', '#80FF00', '#00FF80'
]

const form = ref({
  id: null,
  dataset_id: datasetId.value,
  name: '',
  shortcut_key: '',
  color: '#FF0000',
  sort_order: 0
})

onMounted(async () => {
  await loadData()
})

async function loadData() {
  loading.value = true
  try {
    const [datasetRes, categoriesRes, datasetsRes] = await Promise.all([
      api.get(`/datasets/${datasetId.value}`),
      api.get(`/categories/dataset/${datasetId.value}`),
      api.get('/datasets')
    ])
    dataset.value = datasetRes.data
    categories.value = categoriesRes.data
    // 过滤掉当前数据集
    allDatasets.value = datasetsRes.data.filter(d => d.id !== datasetId.value)
  } finally {
    loading.value = false
  }
}

function showCreateDialog() {
  isEdit.value = false
  form.value = {
    id: null,
    dataset_id: datasetId.value,
    name: '',
    shortcut_key: '',
    color: colorOptions[categories.value.length % colorOptions.length],
    sort_order: categories.value.length
  }
  dialogVisible.value = true
}

function showEditDialog(category) {
  isEdit.value = true
  form.value = { ...category }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.value.name) {
    ElMessage.warning('请填写类别名称')
    return
  }

  try {
    if (isEdit.value) {
      await api.put(`/categories/${form.value.id}`, form.value)
      ElMessage.success('更新成功')
    } else {
      await api.post('/categories', form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

async function handleDelete(category) {
  try {
    await ElMessageBox.confirm(
      `确定要删除类别 "${category.name}" 吗？相关的标注将被清除。`,
      '警告',
      { type: 'warning' }
    )

    await api.delete(`/categories/${category.id}`)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      // 错误已在拦截器中处理
    }
  }
}

function showImportDialog() {
  selectedSourceDataset.value = null
  importDialogVisible.value = true
}

async function handleImportFromDataset() {
  if (!selectedSourceDataset.value) {
    ElMessage.warning('请选择源数据集')
    return
  }

  try {
    const response = await api.post(`/categories/import-from-dataset/${datasetId.value}`, {
      source_dataset_id: selectedSourceDataset.value
    })
    ElMessage.success(response.data.message)
    importDialogVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  }
}

async function handleImportFromConfig() {
  try {
    const response = await api.post(`/dataset-configs/${datasetId.value}/import-default-categories`)
    ElMessage.success(response.data.message)
    loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  }
}

function handleImportCommand(command) {
  if (command === 'dataset') {
    showImportDialog()
  } else if (command === 'config') {
    handleImportFromConfig()
  } else if (command === 'text') {
    batchText.value = ''
    batchTextDialogVisible.value = true
  } else if (command === 'images') {
    batchImageFiles.value = []
    batchImageDialogVisible.value = true
  }
}

async function handleBatchTextImport() {
  if (!batchText.value.trim()) {
    ElMessage.warning('请输入类别名称')
    return
  }
  try {
    const response = await api.post(`/categories/batch-text/${datasetId.value}`, {
      text: batchText.value
    })
    ElMessage.success(`成功导入 ${response.data.length} 个类别`)
    batchTextDialogVisible.value = false
    batchText.value = ''
    loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  }
}

function handleUploadSuccess() {
  ElMessage.success('模板图片上传成功')
  loadData()
}

function handleUploadError() {
  ElMessage.error('模板图片上传失败')
}

async function handleDeleteTemplateImage(category) {
  try {
    await api.delete(`/categories/${category.id}/template-image`)
    ElMessage.success('模板图片已删除')
    loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

function handleBatchImageChange(uploadFile, uploadFiles) {
  batchImageFiles.value = uploadFiles
}

function handleBatchImageRemove(uploadFile, uploadFiles) {
  batchImageFiles.value = uploadFiles
}

async function handleBatchImageImport() {
  if (batchImageFiles.value.length === 0) {
    ElMessage.warning('请选择图片文件')
    return
  }

  batchImageUploading.value = true
  try {
    const formData = new FormData()
    batchImageFiles.value.forEach(file => {
      formData.append('files', file.raw)
    })
    const response = await api.post(`/categories/batch-images/${datasetId.value}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success(response.data.message)
    batchImageDialogVisible.value = false
    batchImageFiles.value = []
    loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    batchImageUploading.value = false
  }
}
</script>

<template>
  <div class="categories-page" v-loading="loading">
    <div class="page-header">
      <div class="header-left">
        <el-button @click="router.push('/admin/datasets')" :icon="'ArrowLeft'">返回</el-button>
        <h2 v-if="dataset">{{ dataset.name }} - 类别管理</h2>
      </div>
      <div class="header-buttons">
        <el-dropdown @command="handleImportCommand" trigger="click">
          <el-button>
            导入类别 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="dataset">从其他数据集导入</el-dropdown-item>
              <el-dropdown-item command="config">从格式配置导入</el-dropdown-item>
              <el-dropdown-item command="text">批量文本导入</el-dropdown-item>
              <el-dropdown-item command="images">批量图片导入</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="primary" @click="showCreateDialog" :icon="'Plus'">
          添加类别
        </el-button>
      </div>
    </div>

    <div class="categories-grid">
      <div
        v-for="category in categories"
        :key="category.id"
        class="category-card"
      >
        <div class="color-bar" :style="{ background: category.color }"></div>
        <div class="card-content">
          <h3>{{ category.name }}</h3>
          <div class="template-section">
            <div v-if="category.template_image_path" class="template-preview">
              <img :src="`/api/categories/${category.id}/template-image`" alt="模板图片" />
            </div>
            <div class="template-actions">
              <el-upload
                :action="`/api/categories/${category.id}/template-image`"
                :headers="uploadHeaders"
                :show-file-list="false"
                :on-success="handleUploadSuccess"
                :on-error="handleUploadError"
                accept="image/*"
              >
                <el-button size="small">
                  {{ category.template_image_path ? '更换模板' : '上传模板' }}
                </el-button>
              </el-upload>
              <el-button
                v-if="category.template_image_path"
                size="small"
                type="danger"
                @click="handleDeleteTemplateImage(category)"
              >删除模板</el-button>
            </div>
          </div>
          <div class="meta">
            <span v-if="category.shortcut_key" class="shortcut">
              快捷键: <kbd>{{ category.shortcut_key }}</kbd>
            </span>
            <span class="order">排序: {{ category.sort_order }}</span>
          </div>
          <div class="actions">
            <el-button size="small" @click="showEditDialog(category)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(category)">删除</el-button>
          </div>
        </div>
      </div>

      <div v-if="categories.length === 0" class="empty-card" @click="showCreateDialog">
        <el-icon :size="32"><Plus /></el-icon>
        <span>添加第一个类别</span>
      </div>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑类别' : '添加类别'" width="400px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="类别名称" />
        </el-form-item>
        <el-form-item label="快捷键">
          <el-input
            v-model="form.shortcut_key"
            placeholder="如: 1, a, q"
            maxlength="1"
            style="width: 100px"
          />
          <div class="form-tip">用于快速选择类别的键盘快捷键</div>
        </el-form-item>
        <el-form-item label="颜色">
          <div class="color-picker">
            <div
              v-for="color in colorOptions"
              :key="color"
              class="color-option"
              :class="{ active: form.color === color }"
              :style="{ background: color }"
              @click="form.color = color"
            />
          </div>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible.value = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 从数据集导入对话框 -->
    <el-dialog v-model="importDialogVisible" title="从其他数据集导入类别" width="400px">
      <el-form label-width="100px">
        <el-form-item label="源数据集">
          <el-select v-model="selectedSourceDataset" placeholder="选择数据集" style="width: 100%">
            <el-option
              v-for="ds in allDatasets"
              :key="ds.id"
              :value="ds.id"
              :label="ds.name"
            />
          </el-select>
        </el-form-item>
        <div class="form-tip" style="margin-left: 100px">
          已存在的类别名称将被跳过
        </div>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleImportFromDataset">导入</el-button>
      </template>
    </el-dialog>

    <!-- 批量文本导入对话框 -->
    <el-dialog v-model="batchTextDialogVisible" title="批量导入类别" width="450px">
      <el-form label-width="100px">
        <el-form-item label="类别列表">
          <el-input
            v-model="batchText"
            type="textarea"
            :rows="12"
            placeholder="每行一个类别名称，例如：&#10;hero&#10;infantry&#10;engineer&#10;sentry&#10;drone"
          />
        </el-form-item>
        <div class="form-tip" style="margin-left: 100px">
          每行一个类别名称，颜色自动分配，重复名称自动跳过
        </div>
      </el-form>
      <template #footer>
        <el-button @click="batchTextDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleBatchTextImport">导入</el-button>
      </template>
    </el-dialog>

    <!-- 批量图片导入对话框 -->
    <el-dialog v-model="batchImageDialogVisible" title="批量图片导入类别" width="500px">
      <div class="batch-image-tip">
        图片文件名（不含扩展名）将作为类别名称，图片自动设为类别模板。
      </div>
      <el-upload
        v-model:file-list="batchImageFiles"
        :auto-upload="false"
        accept="image/*"
        multiple
        :on-change="handleBatchImageChange"
        :on-remove="handleBatchImageRemove"
        list-type="picture"
      >
        <el-button type="primary">选择图片</el-button>
        <template #tip>
          <div class="form-tip">支持 jpg/png/bmp/webp，可多选。重复名称自动跳过。</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="batchImageDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="batchImageUploading"
          :disabled="batchImageFiles.length === 0"
          @click="handleBatchImageImport"
        >
          导入 ({{ batchImageFiles.length }} 张)
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.categories-page {
  background: white;
  padding: 24px;
  border-radius: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h2 {
  margin: 0;
}

.header-buttons {
  display: flex;
  gap: 12px;
}

.categories-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.category-card {
  border: 1px solid #eee;
  border-radius: 8px;
  overflow: hidden;
}

.color-bar {
  height: 8px;
}

.card-content {
  padding: 16px;
}

.card-content h3 {
  margin: 0 0 12px 0;
}

.template-section {
  margin-bottom: 12px;
}

.template-preview {
  margin-bottom: 8px;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f5f5;
  max-width: 200px;
}

.template-preview img {
  width: 100%;
  max-height: 120px;
  object-fit: contain;
  display: block;
}

.template-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.meta {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  color: #666;
  font-size: 13px;
}

.meta kbd {
  padding: 2px 6px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 12px;
}

.actions {
  display: flex;
  gap: 8px;
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
</style>
