<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useAnnotationStore } from '../stores/annotation'
import { useShortcutsStore } from '../stores/shortcuts'
import { usePreannotationReviewStore } from '../stores/preannotationReview'
import { ElMessage, ElMessageBox } from 'element-plus'
import AnnotationCanvas from '../components/AnnotationCanvas.vue'
import CategorySelectionPopup from '../components/CategorySelectionPopup.vue'
import api from '../utils/api'

const route = useRoute()
const router = useRouter()
const store = useAnnotationStore()
const shortcutsStore = useShortcutsStore()
const review = usePreannotationReviewStore()

const datasetId = computed(() => parseInt(route.params.datasetId))
const progress = ref(null)
const showHelp = ref(false)
const showRawOutput = ref(false)
const showShortcutSettings = ref(false)
const editingShortcut = ref(null)
const editingCategoryShortcut = ref(null)  // 正在编辑快捷键的类别ID

// 模式切换（默认拖动模式）
const canvasMode = ref('pan')  // 'annotate' | 'pan'
const zoomLevel = ref(1)
const canvasRef = ref(null)

// RC2026-wulin 模式相关
const pendingAnnotation = ref(null)       // 等待类别选择的标注
const showCategoryPopup = ref(false)      // 类别选择弹窗
const shapeMode = ref('bbox')              // 'bbox' | '4point' | '8point'

const source = ref('manual')
const batches = ref([])
const workspaceLoading = ref(true), actionBusy = ref(false), contextError = ref(false)
const guardPrompt = ref(false)
const loadedDatasetId = ref(null), manualSnapshot = ref('[]'), lastReviewTaskId = ref(null)
let loadedContextKey = '', contextGeneration = 0, disposed = false
const isReviewMode = computed(() => source.value === 'preannotation')
const currentImage = computed(() => isReviewMode.value ? review.image : store.currentImage)
const workAnnotations = computed(() => isReviewMode.value ? review.activeCandidates : store.annotations)
const canvasAnnotations = computed(() => isReviewMode.value ? review.canvasAnnotations : store.annotations)
const canUndo = computed(() => isReviewMode.value ? review.canUndo : store.canUndo)
const canRedo = computed(() => isReviewMode.value ? review.canRedo : store.canRedo)
const canPrevious = computed(() => isReviewMode.value ? !!review.previousId : store.canGoPrevious)
const canNext = computed(() => isReviewMode.value ? !!review.nextId : !(store.isInHistory && !store.canGoNext))
const imageLoading = computed(() => workspaceLoading.value || (isReviewMode.value ? review.loading : store.isLoading))
const editable = computed(() => !imageLoading.value && !actionBusy.value && !guardPrompt.value && (isReviewMode.value ? review.editable && !review.busy : !!currentImage.value))
const dirty = computed(() => isReviewMode.value ? review.dirty : JSON.stringify(store.annotations) !== manualSnapshot.value)
const pendingReviews = computed(() => review.task ? (review.task.counts.succeeded || 0) - review.task.approved - review.task.rejected : 0)
const reviewedCount = computed(() => review.task ? review.task.approved + review.task.rejected : 0)
const reviewProgress = computed(() => review.task?.counts.succeeded ? Math.round(reviewedCount.value / review.task.counts.succeeded * 100) : 0)
const statusLabels = { unreviewed:'待审核',draft:'审核草稿',approved:'已通过',rejected:'已驳回' }
const statusText = computed(() => isReviewMode.value
  ? statusLabels[review.item?.review_status] || (imageLoading.value ? '加载中' : contextError.value ? '加载失败' : '当前队列为空')
  : '人工标注')
const emptyDescription = computed(() => contextError.value ? '加载失败，请重试' : isReviewMode.value
  ? (['queued','running','cancelling'].includes(review.task?.status) ? '批次仍在后台处理，暂无符合条件的结果，可稍后刷新'
    : pendingReviews.value === 0 && review.task?.counts.succeeded ? '当前批次的待审核图片已处理完毕' : '暂无符合筛选条件的预标注结果')
  : '没有更多图片需要标注')

function positive(value) { const n=Number(value); return Number.isInteger(n) && n>0 ? n : undefined }
function contextKey(to) {
  return JSON.stringify([String(to.params.datasetId),to.query.source || 'auto',String(to.query.task || ''),String(to.query.image || ''),
    to.query.review_status || 'pending',to.query.has_candidates || '',to.query.execution_status || 'succeeded'])
}
function contextQuery(extra={}) {
  const query = { ...route.query, source:source.value, ...extra }
  if (isReviewMode.value) {
    query.task = review.task?.id
    query.image = currentImage.value?.id
    Object.assign(query,review.queue,extra)
  } else {
    for (const key of ['task','review_status','has_candidates','execution_status']) delete query[key]
    query.image = currentImage.value?.id
    Object.assign(query,extra)
  }
  for (const key of Object.keys(query)) if (query[key] === undefined || query[key] === null || query[key] === '') delete query[key]
  return query
}
async function syncLocation() {
  const target = { name:'Annotation',params:{datasetId:datasetId.value},query:contextQuery() }
  loadedContextKey = contextKey({ params:target.params,query:target.query })
  await router.replace(target)
}
function preferredBatch() { return batches.value.find(t=>!t.is_sample) || batches.value[0] }
async function loadData(to=route) {
  const token = ++contextGeneration
  workspaceLoading.value = true; contextError.value = false
  try {
    const id = positive(to.params.datasetId)
    if (!id) throw new Error('数据集参数不正确')
    if (loadedDatasetId.value !== id) {
      store.reset(); review.reset()
      await store.loadDatasetConfig(id)
      await store.loadCategories(id)
      const response = await api.get(`/datasets/${id}/preannotation-tasks`,{params:{page_size:100}})
      if (disposed || token !== contextGeneration) return
      batches.value = response.data.items
      // 连续抽样很多次时，也要找到最近一次全量批次。
      let page = 1
      while (!batches.value.some(t=>!t.is_sample) && batches.value.length < response.data.total) {
        const older = await api.get(`/datasets/${id}/preannotation-tasks`,{params:{page_size:100,page:++page}})
        if (disposed || token !== contextGeneration) return
        if (!older.data.items.length) break
        batches.value.push(...older.data.items)
      }
      loadedDatasetId.value = id
    }
    const selectedId = positive(to.query.task)
    const batch = selectedId || preferredBatch()?.id
    const useReview = to.query.source !== 'manual' && !!batch
    source.value = useReview ? 'preannotation' : 'manual'
    if (useReview) {
      await review.load(id,batch,positive(to.query.image),{
        review_status:['pending','unreviewed','draft','approved','rejected','all'].includes(to.query.review_status) ? to.query.review_status : 'pending',
        execution_status:to.query.execution_status || 'succeeded',has_candidates:to.query.has_candidates || ''
      })
      if (disposed || token !== contextGeneration) return
      if (!batches.value.some(t=>t.id===review.task.id)) batches.value.unshift(review.task)
      lastReviewTaskId.value=review.task.id
      canvasMode.value='annotate'
    } else {
      review.reset()
      if (positive(to.query.image)) await store.fetchImage(positive(to.query.image))
      else await store.fetchNextImage(id)
      if (disposed || token !== contextGeneration) return
      if (store.currentImage && store.currentImage.dataset_id !== id) { store.currentImage=null; store.annotations=[]; throw new Error('图片不属于当前数据集') }
      manualSnapshot.value=JSON.stringify(store.annotations)
      canvasMode.value='pan'
    }
    shapeMode.value='bbox'
    pendingAnnotation.value=null; showCategoryPopup.value=false
    await loadProgress()
    if (!disposed && token === contextGeneration) await syncLocation()
  } catch (error) {
    if (!disposed && token === contextGeneration) { contextError.value=true; ElMessage.error(error.response?.data?.detail || '加载标注工作台失败') }
  } finally { if (token === contextGeneration) workspaceLoading.value=false }
}
async function ensureCanLeave() {
  if (guardPrompt.value) return false
  if (!dirty.value) return true
  guardPrompt.value=true
  try {
    await ElMessageBox.confirm(isReviewMode.value ? '保存本图审核草稿后切换？草稿不会计为审核通过。' : '保存当前人工标注后切换？',
      '有未保存的修改',{confirmButtonText:'保存并切换',cancelButtonText:'放弃修改',distinguishCancelAndClose:true,type:'warning'})
    if (isReviewMode.value) return await review.saveDraft()
    await store.saveAnnotations(false); manualSnapshot.value=JSON.stringify(store.annotations)
    return true
  } catch (reason) { return reason === 'cancel' }
  finally { guardPrompt.value=false }
}
async function refreshResults() {
  if (await ensureCanLeave()) await loadData()
}
onBeforeRouteLeave(() => actionBusy.value || review.busy ? false : ensureCanLeave())
onBeforeRouteUpdate(async to => contextKey(to) === loadedContextKey ? true : await ensureCanLeave())
watch(() => contextKey(route), key => { if (key !== loadedContextKey && !disposed) loadData(route) })
function beforeUnload(event) { if (dirty.value) { event.preventDefault(); event.returnValue='' } }
onMounted(async () => {
  window.addEventListener('keydown',handleKeydown)
  window.addEventListener('beforeunload',beforeUnload)
  await loadData()
})
onUnmounted(() => {
  disposed=true; contextGeneration++
  window.removeEventListener('keydown',handleKeydown)
  window.removeEventListener('beforeunload',beforeUnload)
  review.reset(); store.reset()
})
async function changeSource(value) {
  if (actionBusy.value || workspaceLoading.value) return
  const query = { source:value }
  if (value === 'preannotation') query.task=lastReviewTaskId.value || preferredBatch()?.id
  else query.image=currentImage.value?.id
  await router.push({name:'Annotation',params:{datasetId:datasetId.value},query})
}
async function changeBatch(value) {
  await router.push({name:'Annotation',params:{datasetId:datasetId.value},query:{source:'preannotation',task:value,review_status:'pending'}})
}
async function changeReviewFilter(key,value) {
  await router.push({name:'Annotation',params:{datasetId:datasetId.value},query:{...contextQuery({[key]:value}),image:undefined}})
}
async function reviewNavigate(direction) {
  if (!currentImage.value || review.busy || actionBusy.value) return
  try {
    if (review.dirty && !await review.saveDraft()) return
    await review.refreshNavigation(datasetId.value)
    const id = direction === 'previous' ? review.previousId : review.nextId
    if (!id) return ElMessage.info('当前筛选队列中没有更多图片')
    await router.push({name:'Annotation',params:{datasetId:datasetId.value},query:contextQuery({image:id})})
  } catch { /* 拦截器显示错误，保留当前图片和草稿 */ }
}
async function approveReview(action='approve') {
  if (!editable.value || actionBusy.value || showCategoryPopup.value) return
  if (action === 'empty' && review.activeCandidates.length) return ElMessage.warning('请先删除全部候选框，再确认无目标')
  if (action === 'reject') {
    guardPrompt.value=true
    try { await ElMessageBox.confirm('驳回本批次对这张图的结果？已有正式标注会保留。','驳回预标注结果',{type:'warning'}) }
    catch { return }
    finally { guardPrompt.value=false }
  }
  actionBusy.value=true
  try {
    if (!await review.review(action)) return
    ElMessage.success(action==='reject' ? '已驳回本图结果' : '审核通过，正式标注已保存')
    await review.refreshNavigation(datasetId.value)
    const next=review.nextId
    if (next) await router.push({name:'Annotation',params:{datasetId:datasetId.value},query:contextQuery({image:next})})
    else {
      await review.load(datasetId.value,review.task.id,undefined,{...review.queue})
      await syncLocation()
      if (!review.image) ElMessage.info('当前审核队列已处理完毕')
    }
    await loadProgress()
  } catch { /* 保留可恢复状态，不把错误当作审核通过 */ }
  finally { actionBusy.value=false }
}
function undo() { if (editable.value) isReviewMode.value ? review.undo() : store.undo() }
function redo() { if (editable.value) isReviewMode.value ? review.redo() : store.redo() }
function handleAnnotationUpdate(id,changes) { if (editable.value) isReviewMode.value ? review.update(id,changes) : store.updateAnnotation(id,changes) }
function handleAnnotationDelete(id) { if (editable.value) isReviewMode.value ? review.remove(id) : store.removeAnnotation(id) }
function addWithCategory(ann,id) { if (isReviewMode.value) review.add(ann,id); else store.addAnnotationWithCategory(ann,id) }
function changeCandidateCategory(ann,id) { review.update(review.canvasId(ann),{category_id:id}) }
function selectBox(ann) { canvasMode.value='annotate'; canvasRef.value?.selectAnnotation(isReviewMode.value ? review.canvasId(ann) : ann.id) }
function showTaskManager() { router.push({name:'Preannotation',params:{datasetId:datasetId.value},query:{task:review.task?.id,review_status:isReviewMode.value ? review.queue.review_status === 'all' ? '' : review.queue.review_status : '',has_candidates:review.queue.has_candidates,page:route.query.returnPage || 1}}) }

async function loadProgress() {
  try {
    const response = await api.get(`/images/dataset/${datasetId.value}/progress`)
    progress.value = response.data
  } catch (error) {
    console.error('Failed to load progress', error)
  }
}

async function handleSave() {
  if (isReviewMode.value) {
    if (!editable.value) return
    try { if (await review.saveDraft()) ElMessage.success('审核草稿已保存；尚未审核通过') } catch {}
    return
  }
  try {
    const savedCount = await store.saveAnnotations(false)
    ElMessage.success(`保存成功 (${savedCount} 个标注)`)
    // 如果在历史模式，不自动跳转下一张
    if (!store.isInHistory) {
      await store.fetchNextImage(datasetId.value)
      // 进入下一张图片后重置为拖动模式
      canvasMode.value = 'pan'
    }
    manualSnapshot.value=JSON.stringify(store.annotations)
    await syncLocation()
    await loadProgress()
  } catch (error) {
    console.error('Save failed:', error)
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message))
  }
}

async function handleSkip() {
  if (isReviewMode.value) return approveReview('empty')
  try {
    await store.saveAnnotations(true)
    ElMessage.info('已标记为未见')
    await store.fetchNextImage(datasetId.value)
    await loadProgress()
    // 进入下一张图片后重置为拖动模式
    canvasMode.value = 'pan'
    manualSnapshot.value=JSON.stringify(store.annotations)
    await syncLocation()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

async function handlePrevious() {
  if (isReviewMode.value) return reviewNavigate('previous')
  try {
    // 如果已经在历史模式中，先保存当前标注再返回
    if (store.isInHistory) {
      const savedCount = await store.saveAnnotations(false)
      ElMessage.success(`保存成功 (${savedCount} 个标注)`)
    }
    await store.goToPreviousImage()
    manualSnapshot.value=JSON.stringify(store.annotations)
    await syncLocation()
  } catch (error) {
    console.error('Save or navigate failed:', error)
    ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message))
  }
}

async function handleNext() {
  if (isReviewMode.value) return reviewNavigate('next')
  if (store.isInHistory) {
    // 在历史模式中，先保存当前标注，再前往下一张
    try {
      const savedCount = await store.saveAnnotations(false)
      ElMessage.success(`保存成功 (${savedCount} 个标注)`)
      await store.goToNextImage()
      manualSnapshot.value=JSON.stringify(store.annotations)
      await syncLocation()
    } catch (error) {
      console.error('Save or navigate failed:', error)
      ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message))
    }
  } else {
    // 正常流程，继续获取新图片
    await handleSaveAndNext()
  }
}

async function handleSaveAndNext() {
  try {
    await store.saveAnnotations(false)
    ElMessage.success('保存成功')
    store.exitHistoryMode()
    await store.fetchNextImage(datasetId.value)
    await loadProgress()
    // 进入下一张图片后重置为拖动模式
    canvasMode.value = 'pan'
    manualSnapshot.value=JSON.stringify(store.annotations)
    await syncLocation()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

function handleKeydown(e) {
  // 如果类别选择弹窗打开，不处理全局快捷键
  if (showCategoryPopup.value || guardPrompt.value || showRawOutput.value || showHelp.value || showShortcutSettings.value) return

  // 忽略输入框中的按键
  if (['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName) || e.target.isContentEditable) {
    return
  }

  // 正在编辑类别快捷键时，交给对应的处理器
  if (editingCategoryShortcut.value) {
    return
  }

  if (isReviewMode.value && (e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault(); approveReview(); return
  }
  // 使用自定义快捷键
  if (shortcutsStore.matchShortcut(e, 'save')) {
    e.preventDefault()
    handleSave()
    return
  }

  if (shortcutsStore.matchShortcut(e, 'skip')) {
    handleSkip()
    return
  }

  if (shortcutsStore.matchShortcut(e, 'undo')) {
    e.preventDefault()
    undo()
    return
  }

  if (shortcutsStore.matchShortcut(e, 'redo')) {
    e.preventDefault()
    redo()
    return
  }

  if (shortcutsStore.matchShortcut(e, 'help')) {
    showHelp.value = !showHelp.value
    return
  }

  const key = e.key.toLowerCase()

  if (key === 'escape') {
    showHelp.value = false
    showShortcutSettings.value = false
    return
  }

  // 模式切换快捷键
  if (key === 'v') {
    canvasMode.value = 'annotate'
    return
  }
  if (key === 'h') {
    canvasMode.value = 'pan'
    return
  }

  // 数字或字母快捷键选择类别
  const selected = store.selectCategoryByKey(key)
  if (selected) {
    canvasMode.value = 'annotate'
  }
}

// 处理标注添加事件
function handleAnnotationAdd(annotation) {
  if (!editable.value) return
  if (!annotation.category_id) {
    // 未选择类别：暂存标注，弹出类别选择弹窗
    pendingAnnotation.value = annotation
    showCategoryPopup.value = true
  } else {
    // 已选择类别：直接添加
    if (isReviewMode.value) review.add(annotation,annotation.category_id)
    else store.addAnnotation(annotation)
  }
}

// 类别选择弹窗：选中类别
function handleCategorySelected(category) {
  if (pendingAnnotation.value) {
    addWithCategory(pendingAnnotation.value, category.id)
    pendingAnnotation.value = null
  }
  showCategoryPopup.value = false
}

// 类别选择弹窗：取消
function handleCategoryPopupCancel() {
  pendingAnnotation.value = null
  showCategoryPopup.value = false
}

// 快捷键设置相关
function startEditShortcut(action) {
  editingShortcut.value = action
}

function handleShortcutKeydown(e) {
  e.preventDefault()
  if (!editingShortcut.value) return

  if (e.key === 'Escape') {
    editingShortcut.value = null
    return
  }

  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key
  shortcutsStore.updateShortcut(editingShortcut.value, {
    key,
    ctrl: e.ctrlKey || e.metaKey,
    shift: e.shiftKey
  })
  editingShortcut.value = null
  ElMessage.success('快捷键已更新')
}

function resetShortcuts() {
  shortcutsStore.resetToDefault()
  ElMessage.success('快捷键已重置为默认')
}

function selectCategory(category) {
  // 如果正在编辑快捷键，不选择类别
  if (editingCategoryShortcut.value) return
  store.selectedCategory = category
  canvasMode.value = 'annotate'
}

function startEditCategoryShortcut(category, e) {
  e.stopPropagation()
  editingCategoryShortcut.value = category.id
}

function handleCategoryShortcutKeydown(category, e) {
  e.preventDefault()
  e.stopPropagation()

  if (e.key === 'Escape') {
    editingCategoryShortcut.value = null
    return
  }

  // 只接受单个字符或数字
  if (e.key.length === 1) {
    const newKey = e.key.toLowerCase()
    // 检查是否与其他类别快捷键冲突
    const conflict = store.categories.find(c =>
      c.id !== category.id && c.shortcut_key === newKey
    )
    if (conflict) {
      ElMessage.warning(`快捷键 "${newKey}" 已被 "${conflict.name}" 使用`)
      return
    }

    // 更新快捷键
    updateCategoryShortcut(category.id, newKey)
  }
}

async function updateCategoryShortcut(categoryId, shortcutKey) {
  try {
    await api.put(`/categories/${categoryId}`, { shortcut_key: shortcutKey })
    // 更新本地数据
    const cat = store.categories.find(c => c.id === categoryId)
    if (cat) {
      cat.shortcut_key = shortcutKey
    }
    ElMessage.success('快捷键已更新')
  } catch (error) {
    ElMessage.error('更新快捷键失败')
  }
  editingCategoryShortcut.value = null
}

function goBack() {
  if (isReviewMode.value) showTaskManager()
  else router.push('/')
}

function fitToView() {
  if (canvasRef.value) {
    canvasRef.value.fitToContainer()
    zoomLevel.value = canvasRef.value.scale
  }
}

function handleZoomChange(zoom) {
  zoomLevel.value = zoom
}
</script>

<template>
  <div class="annotation-container">
    <!-- 首次加载全屏进度 -->
    <div v-if="!isReviewMode && store.isInitialLoad && store.isPrefetching" class="initial-loading">
      <div class="loading-content">
        <h2>正在加载图片...</h2>
        <el-progress
          :percentage="store.prefetchProgress"
          :stroke-width="20"
          :text-inside="true"
          style="width: 400px"
        />
        <p>预加载中，请稍候</p>
      </div>
    </div>

    <!-- 顶部工具栏 -->
    <header class="toolbar" v-show="isReviewMode || !store.isInitialLoad || !store.isPrefetching">
      <div class="left">
        <el-button @click="goBack" :icon="'ArrowLeft'">返回</el-button>
        <span class="image-info" v-if="currentImage">
          {{ currentImage.filename }}
          <span v-if="currentImage.width">
            ({{ currentImage.width }} x {{ currentImage.height }})
          </span>
        </span>
      </div>
      <div class="center">
        <el-button-group>
          <el-button @click="undo()" :disabled="!canUndo" :icon="'RefreshLeft'">
            撤销
          </el-button>
          <el-button @click="redo()" :disabled="!canRedo" :icon="'RefreshRight'">
            重做
          </el-button>
        </el-button-group>

        <div class="mode-toolbar">
          <el-radio-group v-model="canvasMode" size="small">
            <el-radio-button value="annotate">
              <span class="mode-btn">✏️ 标注 (V)</span>
            </el-radio-button>
            <el-radio-button value="pan">
              <span class="mode-btn">✋ 拖动 (H)</span>
            </el-radio-button>
          </el-radio-group>

          <!-- 形状模式切换 -->
          <el-radio-group
            v-model="shapeMode"
            size="small"
            class="shape-mode-group"
          >
            <el-radio-button value="bbox">矩形</el-radio-button>
            <el-radio-button value="4point">4点</el-radio-button>
            <el-radio-button value="8point">8点</el-radio-button>
          </el-radio-group>

          <span class="zoom-info">{{ Math.round(zoomLevel * 100) }}%</span>
          <el-button size="small" @click="fitToView">适应</el-button>
        </div>
      </div>
      <div class="right">
        <el-button-group class="nav-buttons">
          <el-button @click="handlePrevious" :disabled="!canPrevious || actionBusy || review.busy || imageLoading" :icon="'ArrowLeft'">
            上一张
          </el-button>
          <el-button @click="handleNext" :disabled="!canNext || actionBusy || review.busy || imageLoading" :icon="'ArrowRight'">
            下一张
          </el-button>
        </el-button-group>
        <span v-if="!isReviewMode && store.isInHistory" class="history-indicator">浏览历史中</span>
        <el-button @click="showShortcutSettings = true" :icon="'Setting'">快捷键</el-button>
        <el-button @click="showHelp = true" :icon="'QuestionFilled'">帮助</el-button>
        <el-button @click="handleSkip" type="warning" :disabled="!editable || (isReviewMode && workAnnotations.length > 0)">{{ isReviewMode ? (review.formal.length ? '无新增目标' : '确认无目标') : '未见' }} ({{ shortcutsStore.getShortcutText('skip') }})</el-button>
        <el-button @click="handleSave" :type="isReviewMode ? 'default' : 'primary'" :disabled="!editable" :loading="isReviewMode && review.busy">{{ isReviewMode ? '保存草稿' : '保存' }} ({{ shortcutsStore.getShortcutText('save') }})</el-button>
        <el-button v-if="isReviewMode" type="primary" :disabled="!editable" :loading="actionBusy" @click="approveReview()">审核通过并下一张</el-button>
        <el-button v-if="isReviewMode" type="danger" plain :disabled="!editable" @click="approveReview('reject')">驳回</el-button>
      </div>
    </header>

    <div class="source-bar">
      <div class="source-control">
        <span>标注方式</span>
        <el-radio-group :model-value="source" size="small" :disabled="workspaceLoading || actionBusy || review.busy" @change="changeSource">
          <el-radio-button value="preannotation" :disabled="!batches.length">预标注审核</el-radio-button>
          <el-radio-button value="manual">人工标注</el-radio-button>
        </el-radio-group>
      </div>
      <template v-if="isReviewMode">
        <el-select class="batch-select" aria-label="预标注批次" :model-value="review.task?.id" :disabled="workspaceLoading || actionBusy || review.busy" @change="changeBatch">
          <el-option v-for="batch in batches" :key="batch.id" :value="batch.id" :label="`#${batch.id} ${batch.is_sample ? '抽样' : '全量'} · ${batch.prompt.slice(0,30)}`" />
        </el-select>
        <el-select class="queue-select" aria-label="审核队列" :model-value="review.queue.review_status" :disabled="workspaceLoading || actionBusy || review.busy" @change="value => changeReviewFilter('review_status',value)">
          <el-option label="待审核（含草稿）" value="pending" /><el-option label="尚未编辑" value="unreviewed" /><el-option label="审核草稿" value="draft" /><el-option label="已通过" value="approved" /><el-option label="已驳回" value="rejected" /><el-option label="全部结果" value="all" />
        </el-select>
        <el-select class="queue-select" aria-label="候选框筛选" :model-value="review.queue.has_candidates" placeholder="全部候选结果" :disabled="workspaceLoading || actionBusy || review.busy" @change="value => changeReviewFilter('has_candidates',value)">
          <el-option label="全部候选结果" value="" /><el-option label="存在候选框" value="true" /><el-option label="无候选框" value="false" />
        </el-select>
        <el-tag :type="review.item?.review_status === 'approved' ? 'success' : 'warning'">{{ statusText }}</el-tag>
        <span v-if="dirty" class="unsaved-marker">有未保存修改</span>
        <span class="queue-summary">当前队列 {{ review.queueTotal }} 张</span>
      </template>
      <span v-else class="source-description">保存后完成当前人工标注</span>
      <el-button class="task-link" size="small" @click="showTaskManager">管理预标注任务</el-button>
    </div>

    <!-- 主内容区 -->
    <main class="main-content" v-show="isReviewMode || !store.isInitialLoad || !store.isPrefetching">
      <!-- 左侧类别面板 -->
      <aside class="category-panel">
        <h3>类别选择</h3>
        <div class="mode-hint">
          {{ isReviewMode ? '调整候选框；选择类别可补画漏检目标' : '画框后选择类别' }}
        </div>
        <div class="category-list">
          <div
            v-for="category in store.categories"
            :key="category.id"
            class="category-item"
            :class="{ active: store.selectedCategory?.id === category.id }"
            @click="selectCategory(category)"
          >
            <span class="color-dot" :style="{ background: category.color }"></span>
            <span class="name">{{ category.name }}</span>
            <img
              v-if="category.template_image_path"
              :src="`/api/categories/${category.id}/template-image`"
              class="category-thumb"
              alt=""
            />
            <span
              class="shortcut"
              :class="{ editing: editingCategoryShortcut === category.id }"
              @click="startEditCategoryShortcut(category, $event)"
              @keydown="handleCategoryShortcutKeydown(category, $event)"
              tabindex="0"
            >
              <template v-if="editingCategoryShortcut === category.id">
                ...
              </template>
              <template v-else>
                {{ category.shortcut_key || '+' }}
              </template>
            </span>
          </div>
        </div>

        <div class="annotations-list" v-if="workAnnotations.length > 0">
          <h3>{{ isReviewMode ? review.editable ? '候选框' : '候选记录' : '当前标注' }} ({{ workAnnotations.length }})</h3>
          <div v-for="(ann,index) in workAnnotations" :key="ann.id || ann.client_id" class="annotation-item" @click="selectBox(ann)">
            <span class="index">#{{ index+1 }}</span>
            <el-select v-if="isReviewMode" aria-label="候选框类别" class="candidate-category" size="small" :model-value="ann.category_id" :disabled="!editable" @click.stop @change="value => changeCandidateCategory(ann,value)">
              <el-option v-for="category in store.categories" :key="category.id" :value="category.id" :label="category.name" />
            </el-select>
            <span v-else class="category">{{ store.categories.find(c=>c.id===ann.category_id)?.name || '未知' }}</span>
            <span class="annotation-type-badge" v-if="ann.annotation_type === 'parallelogram'">⬡</span>
            <el-button type="danger" size="small" :icon="'Delete'" circle :disabled="!editable" aria-label="删除标注框" @click.stop="handleAnnotationDelete(isReviewMode ? review.canvasId(ann) : ann.id)" />
          </div>
          <small v-if="isReviewMode" class="panel-note">{{ review.editable ? '点击列表定位框；可修改类别、拖动调整或删除。' : '本批次候选记录只读；通过的框已归入正式标注。' }}</small>
        </div>
        <div v-if="isReviewMode && review.editable && !workAnnotations.length" class="panel-note empty-candidates">{{ review.item?.original_count ? '候选框已全部删除。请检查是否需要补画。' : '模型未发现目标。请检查图片后确认或补画漏检目标。' }}</div>
        <div v-if="isReviewMode && review.formal.length" class="annotations-list formal-list">
          <h3>正式标注 ({{ review.formal.length }})</h3>
          <div v-for="ann in review.formal" :key="ann.id" class="annotation-item">
            <span class="category">{{ store.categories.find(c=>c.id===ann.category_id)?.name || '未知' }}</span><el-tag size="small" type="info">已保存</el-tag>
          </div>
          <small class="panel-note">审核时作为只读参考，已有结果会保留。</small>
        </div>
      </aside>

      <!-- 画布区域 -->
      <div class="canvas-container">
        <div v-if="imageLoading" class="loading-overlay">
          <el-icon class="is-loading" :size="48"><Loading /></el-icon>
        </div>

        <div v-else-if="!currentImage" class="empty-state">
          <el-empty :description="emptyDescription">
            <el-button v-if="isReviewMode" @click="refreshResults">刷新结果</el-button>
            <el-button v-if="isReviewMode && review.queue.review_status !== 'all'" type="primary" @click="changeReviewFilter('review_status','all')">查看全部结果</el-button>
            <el-button @click="goBack">{{ isReviewMode ? '返回任务列表' : '返回首页' }}</el-button>
          </el-empty>
        </div>

        <AnnotationCanvas
          v-else
          ref="canvasRef"
          :image-id="currentImage.id"
          :annotations="canvasAnnotations"
          :categories="store.categories"
          :selected-category="store.selectedCategory"
          :mode="canvasMode"
          :readonly="!editable"
          :allow-draw-without-category="true"
          :shape-mode="shapeMode"
          @add="handleAnnotationAdd"
          @update="handleAnnotationUpdate"
          @delete="handleAnnotationDelete"
          @zoom-change="handleZoomChange"
        />
      </div>

      <!-- 右侧进度面板 -->
      <aside class="progress-panel">
        <template v-if="isReviewMode">
          <h3>预标注审核进度</h3>
          <div v-if="review.task" class="progress-info">
            <el-progress type="circle" :percentage="reviewProgress" :width="120" />
            <div class="stats">
              <div class="stat-row"><span>当前批次</span><span>#{{ review.task.id }}</span></div>
              <div class="stat-row"><span>已产出图片</span><span>{{ review.task.counts.succeeded || 0 }}</span></div>
              <div class="stat-row"><span>待审核 / 草稿</span><span class="warning">{{ pendingReviews }}</span></div>
              <div class="stat-row"><span>已通过</span><span class="success">{{ review.task.approved }}</span></div>
              <div class="stat-row"><span>已驳回</span><span>{{ review.task.rejected }}</span></div>
            </div>
          </div>
          <div class="review-layers"><h4>显示图层</h4><el-checkbox v-model="review.showCandidates">候选框 · 虚线</el-checkbox><el-checkbox v-model="review.showFormal">正式标注 · 实线</el-checkbox></div>
          <div class="review-guidance"><strong>{{ statusText }}</strong><p v-if="!review.ready && currentImage">{{ review.item?.error_message || '这张图片尚未产生可审核的结果，请返回任务页检查。' }}</p><p v-else-if="!review.editable && currentImage">本图已审核，可查看结果；后续正式标注修改请切换人工标注。</p><p v-else>调整候选框后可保存草稿。审核通过才计入正式标注。</p></div>
          <el-button v-if="review.task" size="small" class="review-refresh" :disabled="workspaceLoading || actionBusy || review.busy" @click="refreshResults">刷新当前结果</el-button>
          <el-button v-if="review.item?.raw_response" size="small" class="review-refresh" @click="showRawOutput=true">查看模型输出</el-button>
        </template>
        <template v-else>

        <h3>标注进度</h3>
        <div v-if="progress" class="progress-info">
          <el-progress
            type="circle"
            :percentage="progress.progress"
            :width="120"
          />
          <div class="stats">
            <div class="stat-row">
              <span>总计:</span>
              <span>{{ progress.total }}</span>
            </div>
            <div class="stat-row">
              <span>已标注:</span>
              <span class="success">{{ progress.labeled }}</span>
            </div>
            <div class="stat-row">
              <span>未见:</span>
              <span class="warning">{{ progress.skipped }}</span>
            </div>
            <div class="stat-row">
              <span>待处理:</span>
              <span class="info">{{ progress.pending }}</span>
            </div>
          </div>
        </div>

        <div class="queue-status" v-if="store.queueLength > 0">
          <h4>缓存队列</h4>
          <span class="queue-count">{{ store.queueLength }} 张</span>
        </div>
        </template>
      </aside>
    </main>

    <!-- 后台预加载进度条（底部） -->
    <div v-if="!isReviewMode && !store.isInitialLoad && store.isPrefetching" class="prefetch-bar">
      <span>缓存加载中...</span>
      <el-progress
        :percentage="store.prefetchProgress"
        :stroke-width="6"
        style="width: 200px"
      />
      <span class="queue-info">队列: {{ store.queueLength }}</span>
    </div>

    <!-- 类别选择弹窗 -->
    <CategorySelectionPopup
      :visible="showCategoryPopup"
      :categories="store.categories"
      :current-image-url="currentImage ? `/api/images/${currentImage.id}/file` : ''"
      :pending-annotation="pendingAnnotation"
      @select="handleCategorySelected"
      @cancel="handleCategoryPopupCancel"
    />

    <el-dialog v-model="showRawOutput" title="模型原始输出" width="min(720px, 94vw)"><pre class="raw-output">{{ review.item?.raw_response }}</pre></el-dialog>
    <!-- 快捷键帮助弹窗 -->
    <el-dialog v-model="showHelp" title="快捷键帮助" width="500px">
      <div class="help-content">
        <table class="shortcuts-table">
          <tr v-if="isReviewMode"><td><kbd>Ctrl / ⌘ + Enter</kbd></td><td>审核通过并下一张</td></tr>
          <tr>
            <td><kbd>{{ shortcutsStore.getShortcutText('save') }}</kbd></td>
            <td>{{ isReviewMode ? '保存审核草稿，不审核通过' : '保存当前标注' }}</td>
          </tr>
          <tr>
            <td><kbd>{{ shortcutsStore.getShortcutText('skip') }}</kbd></td>
            <td>{{ isReviewMode ? '确认无目标（须无候选框）' : '标记未见（画面中无目标）' }}</td>
          </tr>
          <tr>
            <td><kbd>{{ shortcutsStore.getShortcutText('undo') }}</kbd></td>
            <td>撤销</td>
          </tr>
          <tr>
            <td><kbd>{{ shortcutsStore.getShortcutText('redo') }}</kbd></td>
            <td>重做</td>
          </tr>
          <tr>
            <td><kbd>Delete</kbd> / <kbd>Backspace</kbd></td>
            <td>删除选中的标注框 / 删除最后一个点</td>
          </tr>
          <tr>
            <td><kbd>鼠标滚轮</kbd></td>
            <td>缩放画布</td>
          </tr>
          <tr>
            <td><kbd>空格</kbd> + 拖动</td>
            <td>平移画布</td>
          </tr>
          <tr>
            <td><kbd>V</kbd></td>
            <td>切换到标注模式</td>
          </tr>
          <tr>
            <td><kbd>H</kbd></td>
            <td>切换到拖动模式</td>
          </tr>
          <tr>
            <td><kbd>类别快捷键</kbd></td>
            <td>快速切换类别并进入标注模式</td>
          </tr>
          <tr>
            <td><kbd>Escape</kbd></td>
            <td>取消当前点标注（4点/8点模式）</td>
          </tr>
          <tr>
            <td><kbd>{{ shortcutsStore.getShortcutText('help') }}</kbd></td>
            <td>显示/隐藏帮助</td>
          </tr>
        </table>
        <div class="help-tip">
          <el-button text type="primary" @click="showHelp = false; showShortcutSettings = true">
            自定义快捷键
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 快捷键设置弹窗 -->
    <el-dialog v-model="showShortcutSettings" title="快捷键设置" width="500px">
      <div class="shortcut-settings">
        <table class="shortcuts-table">
          <tr v-for="(config, action) in shortcutsStore.shortcuts" :key="action">
            <td class="action-name">{{ config.description }}</td>
            <td class="shortcut-key">
              <div
                class="key-input"
                :class="{ editing: editingShortcut === action }"
                @click="startEditShortcut(action)"
                @keydown="handleShortcutKeydown"
                tabindex="0"
              >
                <template v-if="editingShortcut === action">
                  按下新快捷键...
                </template>
                <template v-else>
                  <kbd>{{ shortcutsStore.getShortcutText(action) }}</kbd>
                </template>
              </div>
            </td>
          </tr>
        </table>
        <div class="settings-footer">
          <el-button @click="resetShortcuts">恢复默认</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.annotation-container {
  height: calc(100dvh - 40px);
  display: flex;
  flex-direction: column;
  background: #1a1a2e;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #16213e;
  border-bottom: 1px solid #0f3460;
}

.toolbar .left,
.toolbar .center,
.toolbar .right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mode-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: 16px;
  padding-left: 16px;
  border-left: 1px solid #0f3460;
}

.shape-mode-group {
  margin-left: 4px;
}

.mode-btn {
  font-size: 12px;
}

.zoom-info {
  color: #a0a0a0;
  font-size: 12px;
  min-width: 50px;
  text-align: center;
}

.nav-buttons {
  margin-right: 8px;
}

.history-indicator {
  color: #e6a23c;
  font-size: 12px;
  padding: 4px 8px;
  background: rgba(230, 162, 60, 0.2);
  border-radius: 4px;
}

.image-info {
  color: #a0a0a0;
  font-size: 14px;
}

.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.category-panel,
.progress-panel {
  width: 240px;
  padding: 16px;
  background: #16213e;
  overflow-y: auto;
}

.category-panel h3,
.progress-panel h3 {
  color: white;
  margin-bottom: 16px;
  font-size: 14px;
}

.mode-hint {
  color: #409EFF;
  font-size: 12px;
  margin-bottom: 12px;
  padding: 8px;
  background: rgba(64, 158, 255, 0.1);
  border-radius: 4px;
  text-align: center;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.category-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  background: #0f3460;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.category-item:hover {
  background: #1a4a7a;
}

.category-item.active {
  background: #e94560;
}

.color-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 10px;
  flex-shrink: 0;
}

.category-item .name {
  flex: 1;
  color: white;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-thumb {
  width: 28px;
  height: 28px;
  object-fit: contain;
  border-radius: 3px;
  margin-left: 6px;
  flex-shrink: 0;
}

.category-item .shortcut {
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  font-size: 12px;
  color: #ccc;
  cursor: pointer;
  min-width: 20px;
  text-align: center;
  transition: all 0.2s;
  margin-left: 6px;
  flex-shrink: 0;
}

.category-item .shortcut:hover {
  background: rgba(255, 255, 255, 0.4);
}

.category-item .shortcut.editing {
  background: #e94560;
  color: white;
  outline: none;
}

.category-item .shortcut:focus {
  outline: 2px solid #e94560;
  outline-offset: 2px;
}

.annotations-list {
  margin-top: 24px;
}

.annotation-item {
  display: flex;
  align-items: center;
  padding: 8px;
  background: #0f3460;
  border-radius: 4px;
  margin-bottom: 8px;
}

.annotation-item .index {
  color: #888;
  margin-right: 8px;
}

.annotation-item .category {
  flex: 1;
  color: white;
  font-size: 13px;
}

.annotation-type-badge {
  color: #409EFF;
  margin-right: 4px;
  font-size: 14px;
}

.canvas-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.loading-overlay,
.empty-state {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(26, 26, 46, 0.9);
}

.loading-overlay .el-icon {
  color: #e94560;
}

.progress-panel .progress-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.stats {
  width: 100%;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  color: #a0a0a0;
  border-bottom: 1px solid #0f3460;
}

.stat-row .success {
  color: #67c23a;
}

.stat-row .warning {
  color: #e6a23c;
}

.stat-row .info {
  color: #409eff;
}

.queue-status {
  margin-top: 24px;
  padding: 12px;
  background: #0f3460;
  border-radius: 6px;
}

.queue-status h4 {
  color: #a0a0a0;
  font-size: 12px;
  margin-bottom: 8px;
}

.queue-count {
  color: #67c23a;
  font-size: 18px;
  font-weight: bold;
}

.help-content {
  padding: 16px;
}

.shortcuts-table {
  width: 100%;
  border-collapse: collapse;
}

.shortcuts-table td {
  padding: 10px;
  border-bottom: 1px solid #eee;
}

.shortcuts-table td:first-child {
  width: 200px;
}

kbd {
  display: inline-block;
  padding: 2px 6px;
  background: #f5f5f5;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 12px;
}

/* 首次加载全屏进度 */
.initial-loading {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.loading-content {
  text-align: center;
  color: white;
}

.loading-content h2 {
  margin-bottom: 24px;
}

.loading-content p {
  margin-top: 16px;
  color: #a0a0a0;
}

/* 后台预加载进度条（底部） */
.prefetch-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 32px;
  background: #16213e;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  z-index: 1000;
  color: #a0a0a0;
  font-size: 13px;
}

.prefetch-bar .queue-info {
  color: #67c23a;
}

/* 快捷键设置 */
.shortcut-settings {
  padding: 16px;
}

.shortcuts-table .action-name {
  width: 150px;
}

.shortcuts-table .shortcut-key {
  width: 200px;
}

.key-input {
  padding: 8px 16px;
  background: #f5f5f5;
  border: 2px solid #ddd;
  border-radius: 6px;
  cursor: pointer;
  text-align: center;
  transition: all 0.2s;
}

.key-input:hover {
  border-color: #409eff;
}

.key-input.editing {
  border-color: #e94560;
  background: #fff5f5;
  color: #e94560;
}

.settings-footer {
  margin-top: 24px;
  text-align: center;
}

.help-tip {
  margin-top: 16px;
  text-align: center;
}
</style>

<style scoped>
.source-bar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 16px;background:#102b4c;border-bottom:1px solid #245079;color:#d3ddeb;font-size:12px}.source-control{display:flex;align-items:center;gap:8px}.batch-select{width:280px}.queue-select{width:160px}.unsaved-marker{color:#f7b955}.queue-summary,.source-description{color:#aebed2}.task-link{margin-left:auto}.toolbar{flex-wrap:wrap;gap:10px}.toolbar .left{min-width:0;flex:1 1 220px}.toolbar .center,.toolbar .right{flex-wrap:wrap;gap:8px}.toolbar .image-info{max-width:300px;white-space:nowrap;text-overflow:ellipsis;overflow:hidden}.toolbar .right .el-button+.el-button{margin-left:0}.mode-toolbar{flex-wrap:wrap;gap:8px;margin-left:8px;padding-left:8px}.main-content,.canvas-container{min-height:0;min-width:0}.category-panel,.progress-panel{flex-shrink:0;width:220px}.candidate-category{flex:1;min-width:0}.annotation-item{gap:6px;cursor:pointer}.annotation-item .index{margin-right:0}.panel-note{display:block;color:#9aafc7;font-size:12px;line-height:1.7;margin-top:10px}.empty-candidates{padding:12px;background:#0f3460;border-radius:6px}.review-layers{margin-top:18px;display:flex;flex-direction:column;gap:6px}.review-layers h4{font-size:12px;color:#aebed2}.review-layers :deep(.el-checkbox__label){color:#d3ddeb;font-size:12px}.review-guidance{margin-top:18px;padding:12px;background:#0f3460;border-radius:6px;color:#d3ddeb;font-size:12px;line-height:1.7}.review-guidance strong{color:#f7b955}.review-guidance p{margin-top:6px}.review-refresh{display:block;margin:12px 0 0;width:100%}.raw-output{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto;font-size:12px}.formal-list .annotation-item{cursor:default}@media(max-width:1000px){.category-panel,.progress-panel{width:185px;padding:12px}.source-bar{gap:8px}.batch-select{width:220px}.toolbar{padding:8px}.toolbar .image-info{max-width:220px}}@media(max-width:650px){.annotation-container{height:auto;min-height:calc(100dvh - 40px)}.main-content{flex-direction:column;overflow:visible}.category-panel,.progress-panel{width:100%}.category-list{flex-direction:row;flex-wrap:wrap}.category-item{min-width:120px}.canvas-container{flex:none;height:50vh;min-height:300px}.toolbar .left{flex-basis:100%}.toolbar .right{width:100%}.source-bar{padding:10px}.batch-select,.queue-select{width:calc(50% - 4px)}.source-control{width:100%}.task-link{margin-left:0}.annotations-list{margin-top:12px}.progress-info{align-items:stretch}}
</style>
