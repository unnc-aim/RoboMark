<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '../stores/user'
import api from '../utils/api'
import PreannotationProfileDialog from '../components/PreannotationProfileDialog.vue'
import PreannotationThumbnail from '../components/PreannotationThumbnail.vue'
import ConnectionTestResult from '../components/ConnectionTestResult.vue'

const route = useRoute(), router = useRouter(), user = useUserStore()
const datasetId = Number(route.params.datasetId)
const dataset = ref(null), profiles = ref([]), categories = ref([]), tasks = ref([]), images = ref([])
const loading = ref(true), creating = ref(false), imageLoading = ref(false), polling = ref(true)
const profileDialog = ref(false), editingProfile = ref(null)
const profileId = ref(null), prompt = ref(''), categoryIds = ref([]), shape = ref('bbox'), sampleSize = ref(3)
const testingConnection = ref(false), connectionResult = ref(null)
const selectedTaskId = ref(Number(route.query.task) || null), taskTotal = ref(0), taskPage = ref(1)
const page = ref(1), total = ref(0), overlay = ref(true)
const filters = ref({ has_candidates: '', execution_status: '', review_status: '' })
const selectedTask = computed(() => tasks.value.find(t => t.id === selectedTaskId.value))
const selectedProfile = computed(() => profiles.value.find(p => p.id === profileId.value))
const canEditProfile = computed(() => selectedProfile.value && !selectedProfile.value.environment_key && (user.isAdmin || selectedProfile.value.owner_id === user.user?.id))
const taskLabels = { queued: '排队中', running: '执行中', cancelling: '取消中', cancelled: '已取消', completed: '已完成', completed_with_errors: '部分失败', failed: '失败' }
const executionLabels = { queued: '未处理', running: '处理中', succeeded: '成功', failed: '失败', cancelled: '已取消' }
const reviewLabels = { unreviewed: '待审核', draft: '审核草稿', approved: '已通过', rejected: '已驳回' }
let timer, imageRequest = 0, refreshing = false

function imageParams() {
  const params = { page: page.value, page_size: 24 }
  if (selectedTaskId.value) {
    params.task_id = selectedTaskId.value
    for (const [key, value] of Object.entries(filters.value)) if (value !== '') params[key] = value
  }
  return params
}

async function loadImages(quiet = false) {
  const request = ++imageRequest
  if (!quiet) imageLoading.value = true
  try {
    const response = await api.get(`/datasets/${datasetId}/images`, { params: imageParams() })
    if (request !== imageRequest) return
    images.value = response.data.items
    total.value = response.data.total
  } finally { if (request === imageRequest) imageLoading.value = false }
}

async function loadTasks() {
  const response = await api.get(`/datasets/${datasetId}/preannotation-tasks`, { params: { page: taskPage.value } })
  tasks.value = response.data.items
  taskTotal.value = response.data.total
  if (selectedTaskId.value && !tasks.value.some(t => t.id === selectedTaskId.value)) {
    const selected = await api.get(`/preannotation/tasks/${selectedTaskId.value}`)
    tasks.value = [selected.data, ...tasks.value]
  }
}

async function refresh() {
  if (refreshing) return
  refreshing = true
  try { await loadTasks(); await loadImages(true); polling.value = true }
  catch { polling.value = false }
  finally { refreshing = false }
}

async function chooseTask(id) {
  selectedTaskId.value = id
  page.value = 1
  filters.value = { has_candidates: '', execution_status: '', review_status: '' }
  await router.replace({ query: id ? { task: id } : {} })
  await loadImages()
}

async function filterChanged() { page.value = 1; await loadImages() }

function configure(profile = null) { editingProfile.value = profile; profileDialog.value = true }

watch(profileId, () => { connectionResult.value = null })
async function testConnection() {
  if (!profileId.value || testingConnection.value) return
  const id = profileId.value
  connectionResult.value = null
  testingConnection.value = true
  try {
    const response = await api.post(`/preannotation/profiles/${id}/test`)
    if (id === profileId.value) connectionResult.value = response.data
  } catch { /* 错误统一由拦截器提示 */ }
  finally { testingConnection.value = false }
}

async function profileSaved(profile) {
  connectionResult.value = null
  profiles.value = (await api.get('/preannotation/profiles')).data
  profileId.value = profile?.id || profiles.value[0]?.id || null
}

async function createTask(sample) {
  if (!profileId.value || !prompt.value.trim() || !categoryIds.value.length) return ElMessage.warning('请选择接口、目标类别并填写 Prompt')
  creating.value = true
  try {
    const body = { profile_id: profileId.value, prompt: prompt.value.trim(), annotation_type: shape.value, category_ids: categoryIds.value }
    if (sample) body.sample_size = sampleSize.value
    const response = await api.post(`/datasets/${datasetId}/preannotation-tasks`, body)
    taskPage.value = 1
    await loadTasks()
    await chooseTask(response.data.id)
    polling.value = true
    ElMessage.success(sample ? '抽样任务已提交，可查看叠加效果' : '全量后台任务已提交，关闭页面后继续执行')
  } finally { creating.value = false }
}

async function taskAction(task, action) {
  if (action === 'cancel') {
    try { await ElMessageBox.confirm('取消剩余处理，已生成的结果仍可审核。', '取消预标注任务', { type: 'warning' }) }
    catch { return }
  }
  await api.post(`/preannotation/tasks/${task.id}/${action}`)
  await refresh()
}

function openImage(image) {
  if (!selectedTaskId.value) return router.push(`/annotate/${datasetId}`)
  const query = Object.fromEntries(Object.entries(filters.value).filter(([,value]) => value !== ''))
  router.push({ name: 'PreannotationReview', params: { datasetId, taskId: selectedTaskId.value, imageId: image.id }, query })
}

onMounted(async () => {
  try {
    const [d,p,c] = await Promise.all([api.get(`/datasets/${datasetId}`), api.get('/preannotation/profiles'), api.get(`/categories/dataset/${datasetId}`)])
    dataset.value = d.data; profiles.value = p.data; categories.value = c.data
    profileId.value = profiles.value[0]?.id || null; categoryIds.value = categories.value.map(c => c.id)
    await loadTasks(); await loadImages()
    timer = setInterval(() => { if (polling.value && !document.hidden) refresh() }, 4000)
  } catch { polling.value = false }
  finally { loading.value = false }
})
onUnmounted(() => { clearInterval(timer); imageRequest++ })
</script>

<template>
  <div class="preannotation-page" v-loading="loading">
    <header class="page-header">
      <div><el-button link @click="router.push(user.isAdmin ? '/admin/datasets' : '/')">← {{ user.isAdmin ? '数据集管理' : '数据集' }}</el-button><h1>{{ dataset?.name || '数据集' }} · 预标注</h1><p>输入识别要求，后台批量生成候选框，再由你审核。</p></div>
      <el-button @click="router.push(`/annotate/${datasetId}`)">人工标注</el-button>
    </header>
    <el-alert v-if="!polling" title="自动刷新已暂停，请检查服务后点击刷新。" type="warning" :closable="false" show-icon />
    <section class="generation-panel">
      <div class="section-title"><h2>创建预标注任务</h2><span>关闭页面不影响后台任务</span></div>
      <el-form label-position="top" @submit.prevent>
        <div class="config-grid">
          <el-form-item label="推理接口"><div class="interface-picker"><el-select v-model="profileId" placeholder="选择接口配置"><el-option v-for="p in profiles" :key="p.id" :value="p.id" :label="`${p.name}${p.is_shared ? '（共享）' : ''}`" /></el-select><el-button @click="configure()">添加</el-button><el-button :disabled="!canEditProfile" @click="configure(selectedProfile)">编辑</el-button><el-button :disabled="!profileId" :loading="testingConnection" @click="testConnection">测试连接</el-button></div></el-form-item>
          <el-form-item label="输出形状"><el-select v-model="shape"><el-option value="bbox" label="矩形框" /><el-option value="parallelogram" label="四点框" /></el-select></el-form-item>
          <el-form-item label="目标类别"><el-select v-model="categoryIds" multiple collapse-tags collapse-tags-tooltip placeholder="选择当前数据集的类别"><el-option v-for="c in categories" :key="c.id" :value="c.id" :label="c.name" /></el-select></el-form-item>
        </div>
        <ConnectionTestResult :result="connectionResult" />
        <el-alert v-if="!categories.length" title="该数据集尚无类别，请先配置类别。" type="warning" :closable="false"><el-button v-if="user.isAdmin" link @click="router.push(`/admin/categories/${datasetId}`)">配置类别</el-button></el-alert>
        <el-form-item label="Prompt"><el-input v-model="prompt" type="textarea" :rows="3" :maxlength="12000" placeholder="例如：标注图片中的所有无人机，框住完整机身；忽略鸟类和远处无法辨认的物体。" /></el-form-item>
        <div class="generation-actions"><span>抽样图片</span><el-input-number v-model="sampleSize" :min="1" :max="20" size="small" /><el-button :loading="creating" @click="createTask(true)">抽样验证</el-button><el-button type="primary" :loading="creating" @click="createTask(false)">对整个数据集运行</el-button><small>已有人工标注保留；每次运行产生一个新批次。</small></div>
      </el-form>
    </section>
    <section class="tasks-panel">
      <div class="section-title"><h2>任务批次</h2><el-button size="small" @click="refresh">刷新</el-button></div>
      <el-empty v-if="!tasks.length" description="尚未创建任务，先试运行几张图片" :image-size="65" />
      <el-table v-else :data="tasks" size="small" @row-click="task => chooseTask(task.id)">
        <el-table-column label="批次" width="115"><template #default="{row}"><el-tag :type="selectedTaskId === row.id ? 'primary' : 'info'">#{{ row.id }} {{ row.is_sample ? '抽样' : '全量' }}</el-tag></template></el-table-column>
        <el-table-column prop="prompt" label="Prompt" min-width="180" show-overflow-tooltip />
        <el-table-column label="进度" min-width="155"><template #default="{row}"><el-progress :percentage="Math.round(row.processed_images / row.total_images * 100)" :stroke-width="5" /><small>{{ row.processed_images }} / {{ row.total_images }} 张</small></template></el-table-column>
        <el-table-column label="状态" width="115"><template #default="{row}">{{ taskLabels[row.status] }}</template></el-table-column>
        <el-table-column label="结果 / 空 / 失败" width="145"><template #default="{row}">{{ row.with_results }} / {{ row.empty_results }} / {{ row.counts.failed || 0 }}</template></el-table-column>
        <el-table-column label="操作" width="180"><template #default="{row}"><el-button link type="primary" @click.stop="chooseTask(row.id)">查看结果</el-button><el-button v-if="(user.isAdmin || row.created_by === user.user?.id) && ['queued','running'].includes(row.status)" link type="danger" @click.stop="taskAction(row,'cancel')">取消</el-button><el-button v-if="(user.isAdmin || row.created_by === user.user?.id) && row.counts.failed && row.status !== 'cancelled'" link @click.stop="taskAction(row,'retry-failed')">重试失败</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-if="taskTotal > 20" v-model:current-page="taskPage" :total="taskTotal" :page-size="20" layout="prev,pager,next" @current-change="loadTasks" />
    </section>
    <section class="images-panel" v-loading="imageLoading">
      <div class="section-title"><h2>{{ selectedTask ? `批次 #${selectedTask.id} · 图片与审核` : '数据集图片' }}</h2><el-switch v-model="overlay" active-text="叠加候选框" /></div>
      <div class="filters"><el-select :model-value="selectedTaskId" clearable placeholder="选择任务批次" @change="chooseTask"><el-option v-for="t in tasks" :key="t.id" :value="t.id" :label="`#${t.id} ${t.is_sample ? '抽样' : '全量'} · ${t.prompt}`" /></el-select><el-select v-model="filters.has_candidates" placeholder="所有候选结果" :disabled="!selectedTaskId" @change="filterChanged"><el-option label="所有候选结果" value="" /><el-option label="存在候选框" value="true" /><el-option label="无候选框" value="false" /></el-select><el-select v-model="filters.execution_status" placeholder="所有执行状态" :disabled="!selectedTaskId" @change="filterChanged"><el-option label="所有执行状态" value="" /><el-option v-for="(label,value) in executionLabels" :key="value" :label="label" :value="value" /></el-select><el-select v-model="filters.review_status" placeholder="所有审核状态" :disabled="!selectedTaskId" @change="filterChanged"><el-option label="所有审核状态" value="" /><el-option v-for="(label,value) in reviewLabels" :key="value" :label="label" :value="value" /></el-select><span>{{ total }} 张</span></div>
      <el-empty v-if="!images.length" description="没有符合条件的图片" />
      <div class="image-grid"><button v-for="image in images" :key="image.id" class="image-card" @click="openImage(image)"><PreannotationThumbnail :image="image" :categories="categories" :overlay="overlay" /><div class="image-card-body"><strong :title="image.filename">{{ image.filename }}</strong><div v-if="image.execution_status"><el-tag size="small" :type="image.execution_status === 'failed' ? 'danger' : 'info'">{{ executionLabels[image.execution_status] }}</el-tag><el-tag v-if="image.execution_status === 'succeeded'" size="small" :type="image.review_status === 'approved' ? 'success' : 'warning'">{{ reviewLabels[image.review_status] }}</el-tag></div><small v-if="image.execution_status === 'succeeded'">{{ image.candidates.length }} 个候选框<span v-if="image.original_count === 0"> · 模型未发现目标</span><span v-else-if="!image.candidates.length"> · 已删除全部候选</span></small><small v-if="image.error_message" class="image-error" :title="image.error_message">{{ image.error_message }}</small></div></button></div>
      <el-pagination v-model:current-page="page" :total="total" :page-size="24" layout="prev,pager,next,total" @current-change="loadImages()" />
    </section>
    <PreannotationProfileDialog v-model="profileDialog" :profile="editingProfile" @saved="profileSaved" />
  </div>
</template>

<style scoped>
.preannotation-page{width:100%;min-width:0;color:#263445}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}.page-header h1{font-size:26px;margin:12px 0 8px}.page-header p{color:#64748b;margin:0}section{background:white;border:1px solid #e6eaf0;border-radius:12px;padding:22px;margin-top:20px}.section-title{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:18px}.section-title h2{font-size:18px;margin:0}.section-title>span{font-size:13px;color:#64748b}.config-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,.7fr) minmax(0,1fr);gap:22px}.config-grid :deep(.el-select){width:100%}.interface-picker{display:flex;flex-wrap:wrap;width:100%;gap:8px}.interface-picker .el-select{flex:1 1 150px;min-width:0}.interface-picker .el-button+.el-button{margin-left:0}.generation-actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.generation-actions small{color:#64748b}.filters{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:22px}.filters .el-select{width:170px}.filters .el-select:first-child{width:250px}.filters>span{margin-left:auto;color:#64748b}.image-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}.image-card{display:block;text-align:left;padding:0;border:1px solid #e3e8ee;border-radius:8px;overflow:hidden;background:white;cursor:pointer;color:inherit;transition:box-shadow .15s}.image-card:hover{box-shadow:0 3px 16px #21354718;border-color:#8cb4e8}.image-card-body{padding:13px;display:flex;flex-direction:column;gap:10px}.image-card strong{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.image-card-body>div{display:flex;gap:7px;flex-wrap:wrap}.image-card small{color:#64748b;line-height:1.5}.image-card .image-error{color:#c24141;max-height:40px;overflow:hidden}.el-pagination{justify-content:center;margin-top:24px}.tasks-panel :deep(.el-table__row){cursor:pointer}@media(max-width:1000px){.image-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.config-grid{grid-template-columns:1fr 1fr}.config-grid>div:first-child{grid-column:1/-1}}@media(max-width:650px){.preannotation-page{padding:0}.image-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.config-grid{grid-template-columns:1fr}.config-grid>div:first-child{grid-column:auto}section{padding:14px}.filters .el-select,.filters .el-select:first-child{width:calc(50% - 6px)}.page-header h1{font-size:20px}.page-header{gap:10px}.section-title>span{display:none}}
</style>
