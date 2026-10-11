<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../utils/api'
import AnnotationCanvas from '../components/AnnotationCanvas.vue'

const route = useRoute(), router = useRouter()
const datasetId = Number(route.params.datasetId), taskId = Number(route.params.taskId)
const imageId = computed(() => Number(route.params.imageId))
const state = ref(null), categories = ref([]), candidates = ref([]), loading = ref(true), busy = ref(false), dirty = ref(false)
const categoryId = ref(null), mode = ref('annotate'), shapeMode = ref('bbox'), showCandidates = ref(true), showFormal = ref(true)
const canvas = ref(null), history = ref([]), historyIndex = ref(-1)
const activeCandidates = computed(() => candidates.value.filter(a => !a.is_deleted))
const ready = computed(() => state.value?.task_image.execution_status === 'succeeded')
const editable = computed(() => ready.value && ['unreviewed', 'draft'].includes(state.value.task_image.review_status))
const selectedCategory = computed(() => categories.value.find(c => c.id === categoryId.value))
const reviewLabels = { unreviewed: '待审核', draft: '审核草稿', approved: '已通过', rejected: '已驳回' }
const executionLabels = { queued: '未处理', running: '处理中', succeeded: '成功', failed: '失败', cancelled: '已取消' }
const canvasAnnotations = computed(() => {
  const formal = showFormal.value ? (state.value?.annotations || []).map(a => ({ ...a, id: `formal-${a.id}`, is_readonly: true })) : []
  const visible = showCandidates.value ? activeCandidates.value.map(a => ({ ...a, id: `candidate-${a.id || a.client_id}`, is_candidate: true, is_readonly: !editable.value })) : []
  // 审核通过后以正式标注为准，避免重复叠加同一框。
  return [...formal, ...(state.value?.task_image.review_status === 'approved' ? [] : visible)]
})
let timer, loadToken = 0
const endpoint = () => `/preannotation/tasks/${taskId}/images/${imageId.value}`

function record() {
  history.value = history.value.slice(0, historyIndex.value + 1)
  history.value.push(JSON.stringify(candidates.value))
  if (history.value.length > 50) history.value.shift()
  historyIndex.value = history.value.length - 1
  dirty.value = true
}

function undo() { if (historyIndex.value > 0) { historyIndex.value--; candidates.value = JSON.parse(history.value[historyIndex.value]); dirty.value = true } }
function redo() { if (historyIndex.value < history.value.length - 1) { historyIndex.value++; candidates.value = JSON.parse(history.value[historyIndex.value]); dirty.value = true } }
function candidateByCanvasId(id) { return candidates.value.find(a => `candidate-${a.id || a.client_id}` === id) }
function update(id, values) { if (!editable.value) return; const ann = candidateByCanvasId(id); if (ann) { Object.assign(ann, values); record() } }
function remove(id) { update(id, { is_deleted: true }) }
function changeCategory(ann, value) { ann.category_id = value; record() }

function add(annotation) {
  if (!editable.value || !categoryId.value) return
  candidates.value.push({ ...annotation, category_id: categoryId.value, client_id: crypto.randomUUID(), is_manual: true, is_deleted: false })
  record()
  shapeMode.value = 'bbox'
}

function applyState(data) {
  state.value = data
  candidates.value = data.candidates
  history.value = [JSON.stringify(candidates.value)]
  historyIndex.value = 0
  dirty.value = false
}

async function load() {
  const token = ++loadToken
  loading.value = true
  try { const response = await api.get(endpoint()); if (token === loadToken) applyState(response.data) }
  finally { if (token === loadToken) loading.value = false }
}

async function saveDraft() {
  if (!editable.value || busy.value) return false
  const annotations = candidates.value.map(a => {
    const data = Object.fromEntries(['id','category_id','annotation_type','x_center','y_center','width','height',
      'p1_x','p1_y','p2_x','p2_y','p3_x','p3_y','p4_x','p4_y','is_deleted'].filter(k => a[k] !== undefined).map(k => [k,a[k]]))
    return data
  })
  busy.value = true
  try {
    const response = await api.put(endpoint() + '/draft', { revision: state.value.task_image.revision, annotations })
    applyState(response.data)
    ElMessage.success('审核草稿已保存')
    return true
  } catch { return false }
  finally { busy.value = false }
}

async function navigate(direction, persist = true) {
  if (persist && dirty.value && !await saveDraft()) return
  const params = { task_id: taskId, page_size: 1, [direction === 'previous' ? 'before_id' : 'after_id']: imageId.value }
  for (const key of ['has_candidates','execution_status','review_status']) if (route.query[key]) params[key] = route.query[key]
  const response = await api.get(`/datasets/${datasetId}/images`, { params })
  if (response.data.items.length) {
    await router.push({ name: 'PreannotationReview', params: { datasetId, taskId, imageId: response.data.items[0].id }, query: route.query })
  } else ElMessage.info(direction === 'previous' ? '当前筛选中没有更早的图片' : '当前筛选中的图片已浏览完毕')
}

async function review(action) {
  if (!editable.value || busy.value) return
  if (action === 'empty' && activeCandidates.value.length) return ElMessage.warning('请先删除全部候选框，再确认无目标')
  if (dirty.value && !await saveDraft()) return
  busy.value = true
  try {
    const response = await api.post(endpoint() + '/review', { revision: state.value.task_image.revision,
      image_revision: state.value.image.annotation_revision, action })
    applyState(response.data)
    ElMessage.success(action === 'reject' ? '该批次结果已驳回' : '审核通过，正式标注已保存')
  } catch { return }
  finally { busy.value = false }
  await navigate('next', false)
}

async function guard() {
  if (!dirty.value) return true
  try { await ElMessageBox.confirm('你有未保存的候选框修改。保存草稿后离开？', '未保存的审核草稿', { confirmButtonText: '保存并离开', cancelButtonText: '继续编辑', type: 'warning' }) }
  catch { return false }
  return await saveDraft()
}
onBeforeRouteLeave(guard)
onBeforeRouteUpdate(guard)
function beforeUnload(event) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
function keydown(event) {
  if (['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName) || event.target.isContentEditable || !editable.value) return
  if (event.ctrlKey || event.metaKey) {
    if (event.key.toLowerCase() === 's') { event.preventDefault(); saveDraft() }
    if (event.key.toLowerCase() === 'z') { event.preventDefault(); event.shiftKey ? redo() : undo() }
  }
}
watch(imageId, load)
onMounted(async () => {
  try { categories.value = (await api.get(`/categories/dataset/${datasetId}`)).data; categoryId.value = categories.value[0]?.id || null; await load() }
  finally { loading.value = false }
  window.addEventListener('keydown', keydown); window.addEventListener('beforeunload', beforeUnload)
  timer = setInterval(async () => {
    if (!ready.value && !loading.value && !dirty.value && !document.hidden) {
      try { await load() } catch { clearInterval(timer) }
    }
  }, 4000)
})
onUnmounted(() => { clearInterval(timer); loadToken++; window.removeEventListener('keydown',keydown); window.removeEventListener('beforeunload',beforeUnload) })
</script>

<template>
  <div class="review-page" v-loading="loading">
    <header class="review-header"><div><el-button link @click="router.push({ name: 'Preannotation', params: { datasetId }, query: { task: taskId } })">← 返回图片列表</el-button><h1>{{ state?.image.filename || '图片审核' }}</h1><span>批次 #{{ taskId }} · {{ executionLabels[state?.task_image.execution_status] }}<template v-if="ready"> · {{ reviewLabels[state?.task_image.review_status] }}</template><em v-if="dirty"> · 有未保存修改</em></span></div><div class="nav"><el-button :disabled="busy" @click="navigate('previous')">上一张</el-button><el-button :disabled="busy" @click="navigate('next')">下一张</el-button></div></header>
    <el-alert v-if="state && !ready" :title="state.task_image.error_message || '该图片尚未产生通过验证的预标注结果，可稍后刷新或返回列表查看任务。'" :type="state.task_image.execution_status === 'failed' ? 'error' : 'info'" :closable="false" show-icon />
    <div class="review-workspace">
      <div class="canvas-column"><div class="canvas-toolbar"><el-radio-group v-model="mode" size="small" :disabled="!editable"><el-radio-button value="annotate">编辑 / 补画</el-radio-button><el-radio-button value="pan">平移</el-radio-button></el-radio-group><el-radio-group v-model="shapeMode" size="small" :disabled="!editable"><el-radio-button value="bbox">矩形 / 调整</el-radio-button><el-radio-button value="4point">补画四点框</el-radio-button></el-radio-group><el-button size="small" @click="canvas?.fitToContainer()">适应图片</el-button><el-button size="small" :disabled="!editable || historyIndex <= 0" @click="undo">撤销</el-button><el-button size="small" :disabled="!editable || historyIndex >= history.length-1" @click="redo">重做</el-button></div>
        <div class="canvas-area"><AnnotationCanvas v-if="state" :key="state.image.id" ref="canvas" :image-id="state.image.id" :annotations="canvasAnnotations" :categories="categories" :selected-category="selectedCategory" :mode="mode" :shape-mode="shapeMode" :readonly="!editable" @add="add" @update="update" @delete="remove" /></div>
        <div class="layer-controls"><el-checkbox v-model="showFormal">正式标注 · 实线（{{ state?.annotations.length || 0 }}）</el-checkbox><el-checkbox v-model="showCandidates">候选框 · 虚线（{{ activeCandidates.length }}）</el-checkbox><span>滚轮缩放 · 空格拖动平移</span></div>
      </div>
      <aside class="candidate-panel"><h2>审核候选框</h2><el-form label-position="top"><el-form-item label="补画使用的类别"><el-select v-model="categoryId" :disabled="!editable"><el-option v-for="c in categories" :key="c.id" :value="c.id" :label="c.name" /></el-select></el-form-item></el-form>
        <p v-if="ready && !activeCandidates.length" class="empty-result">{{ state.task_image.original_count ? '全部候选框已删除。可补画漏检目标，或确认无目标。' : '模型未发现目标。请检查图片，补画漏检目标或确认无目标。' }}</p>
        <div class="candidate-list"><div v-for="(ann,index) in activeCandidates" :key="ann.id || ann.client_id" class="candidate-row"><div class="candidate-row-header"><strong>#{{ index+1 }} {{ ann.annotation_type === 'parallelogram' ? '四点框' : '矩形' }}</strong><small v-if="ann.is_manual">人工补画</small></div><el-select :model-value="ann.category_id" :disabled="!editable" size="small" @change="value => changeCategory(ann,value)"><el-option v-for="c in categories" :key="c.id" :value="c.id" :label="c.name" /></el-select><el-button :disabled="!editable" type="danger" link @click="remove(`candidate-${ann.id || ann.client_id}`)">删除</el-button></div></div>
        <div class="review-actions"><el-button :disabled="!editable" :loading="busy" @click="saveDraft">保存草稿</el-button><el-button type="primary" :disabled="!editable" :loading="busy" @click="review('approve')">通过并下一张</el-button><el-button :disabled="!editable || activeCandidates.length > 0" :loading="busy" @click="review('empty')">确认无目标</el-button><el-button type="danger" plain :disabled="!editable" :loading="busy" @click="review('reject')">驳回本次结果</el-button></div>
        <p class="review-note">通过后追加到正式标注，已有人工标注保留。保存草稿不计入已完成标注。</p>
      </aside>
    </div>
    <el-collapse v-if="state" class="diagnostics"><el-collapse-item title="查看模型原始输出与验证信息" name="raw"><pre>{{ state.task_image.raw_response || state.task_image.error_message || '暂无模型响应' }}</pre></el-collapse-item></el-collapse>
  </div>
</template>

<style scoped>
.review-page{padding:22px;background:#f5f7fa;min-height:100vh;color:#263445}.review-header{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:20px}.review-header h1{font-size:22px;margin:10px 0}.review-header span{color:#64748b;font-size:13px}.review-header em{color:#bd6800;font-style:normal}.nav{display:flex;white-space:nowrap}.review-workspace{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:18px;margin-top:16px}.canvas-column,.candidate-panel{background:white;border:1px solid #e6eaf0;border-radius:10px;overflow:hidden}.canvas-toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:14px}.canvas-toolbar .el-button+.el-button{margin-left:0}.canvas-area{height:65vh;min-height:420px;background:#e5e7eb}.layer-controls{display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:12px 16px}.layer-controls>span{font-size:12px;color:#64748b}.candidate-panel{padding:18px}.candidate-panel h2{font-size:17px;margin:0 0 20px}.candidate-panel :deep(.el-select){width:100%}.candidate-list{max-height:36vh;overflow:auto}.candidate-row{padding:12px 0;border-bottom:1px solid #edf0f4;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px}.candidate-row>.candidate-row-header{grid-column:1/-1;display:flex;justify-content:space-between;font-size:13px}.candidate-row small{color:#64748b}.review-actions{display:grid;grid-template-columns:1fr;gap:10px;margin-top:20px}.review-actions .el-button+.el-button{margin-left:0}.review-note,.empty-result{font-size:13px;color:#64748b;line-height:1.7}.diagnostics{margin-top:20px}.diagnostics pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:350px;overflow:auto;font-size:12px}@media(max-width:850px){.review-workspace{grid-template-columns:1fr}.canvas-area{height:55vh;min-height:320px}.candidate-list{max-height:300px}.review-page{padding:12px}.review-header h1{font-size:18px;overflow-wrap:anywhere}.review-actions{grid-template-columns:1fr 1fr}}
</style>
